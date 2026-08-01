import sqlite3
import tempfile
import time
from pathlib import Path
from contextlib import closing

# Let's define the original baseline function
def run_baseline(db_path: str):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        processing_folders = conn.execute(
            "SELECT id FROM folders WHERE status = 'processing'"
        ).fetchall()
        for folder in processing_folders:
            folder_id = int(folder["id"])
            unprocessed = conn.execute(
                """SELECT COUNT(*) AS c FROM images
                WHERE folder_id = ? AND metadata_json IS NULL AND error IS NULL""",
                (folder_id,),
            ).fetchone()
            if unprocessed and unprocessed["c"] == 0:
                conn.execute(
                    "UPDATE folders SET status = 'completed' WHERE id = ?",
                    (folder_id,),
                )
        conn.commit()

# Let's define the optimized function using a single set-based SQL UPDATE query with NOT EXISTS
def run_optimized(db_path: str):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """UPDATE folders
               SET status = 'completed'
               WHERE status = 'processing'
                 AND NOT EXISTS (
                     SELECT 1 FROM images
                     WHERE images.folder_id = folders.id
                       AND images.metadata_json IS NULL
                       AND images.error IS NULL
                 )"""
        )
        conn.commit()

def setup_db(db_path: str, num_folders: int = 100, num_images_per_folder: int = 100):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("DROP TABLE IF EXISTS images")
        conn.execute("DROP TABLE IF EXISTS folders")
        conn.execute("""
            CREATE TABLE folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'idle'
            )
        """)
        conn.execute("""
            CREATE TABLE images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
                rel_path TEXT NOT NULL,
                error TEXT,
                metadata_json TEXT,
                UNIQUE(folder_id, rel_path)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_images_folder ON images(folder_id)")

        # Insert folders
        folders_data = []
        for i in range(num_folders):
            # 50% are 'processing', 50% are 'idle' or 'completed'
            status = 'processing' if i % 2 == 0 else 'idle'
            folders_data.append((f"/path/to/folder_{i}", status))

        conn.executemany("INSERT INTO folders (path, status) VALUES (?, ?)", folders_data)

        # Insert images
        images_data = []
        for f_idx in range(1, num_folders + 1):
            is_processing = (f_idx - 1) % 2 == 0
            # For processing folders, let's make some of them fully processed and some not.
            # E.g., if f_idx % 4 == 1, all images are processed (no unprocessed).
            # If f_idx % 4 == 3, some images are unprocessed.
            is_fully_processed = (f_idx - 1) % 4 == 0

            for img_idx in range(num_images_per_folder):
                rel_path = f"img_{img_idx}.png"
                if is_processing:
                    if is_fully_processed:
                        # Processed image (has metadata_json)
                        metadata_json = '{"processed": true}'
                        error = None
                    else:
                        # 5% of images in this folder are unprocessed (NULL metadata_json and NULL error)
                        if img_idx < 5:
                            metadata_json = None
                            error = None
                        else:
                            metadata_json = '{"processed": true}'
                            error = None
                else:
                    # Non-processing folders can have mixed
                    metadata_json = None
                    error = None

                images_data.append((f_idx, rel_path, error, metadata_json))

        conn.executemany(
            "INSERT INTO images (folder_id, rel_path, error, metadata_json) VALUES (?, ?, ?, ?)",
            images_data
        )
        conn.commit()

def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_perf.db")

        print("--- SETUP DATABASE ---")
        num_folders = 100
        num_images_per_folder = 100
        print(f"Folders: {num_folders} (50 'processing')")
        print(f"Images per folder: {num_images_per_folder} (Total: {num_folders * num_images_per_folder})")

        # Test baseline
        setup_db(db_path, num_folders, num_images_per_folder)
        start_time = time.perf_counter()
        run_baseline(db_path)
        baseline_time = time.perf_counter() - start_time

        # Verify baseline results
        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            baseline_completed = [
                row["id"] for row in conn.execute(
                    "SELECT id FROM folders WHERE status = 'completed'"
                ).fetchall()
            ]

        # Test optimized
        setup_db(db_path, num_folders, num_images_per_folder)
        start_time = time.perf_counter()
        run_optimized(db_path)
        optimized_time = time.perf_counter() - start_time

        # Verify optimized results
        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            optimized_completed = [
                row["id"] for row in conn.execute(
                    "SELECT id FROM folders WHERE status = 'completed'"
                ).fetchall()
            ]

        print("\n--- RESULTS ---")
        print(f"Baseline (N+1 queries) Time : {baseline_time * 1000:.3f} ms")
        print(f"Optimized (1 query) Time   : {optimized_time * 1000:.3f} ms")
        speedup = (baseline_time / optimized_time) if optimized_time > 0 else float('inf')
        print(f"Speedup                     : {speedup:.2f}x")

        print("\n--- VERIFICATION ---")
        print(f"Baseline completed folders : {sorted(baseline_completed)}")
        print(f"Optimized completed folders: {sorted(optimized_completed)}")
        if sorted(baseline_completed) == sorted(optimized_completed):
            print("SUCCESS: Results match exactly!")
        else:
            print("FAILURE: Results differ!")

if __name__ == "__main__":
    main()
