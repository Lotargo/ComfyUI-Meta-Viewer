type ViewMode = 'list' | 'grid' | 'gallery';

interface ImageListItem {
  id?: number;
  file_name: string;
  file?: string;
  path?: string;
  format?: string | null;
  size?: number[] | null;
  mode?: string | null;
  error?: string | null;
  thumbnail?: string | null;
}

interface ImageDetail extends ImageListItem {
  prompt_parameters?: Record<string, unknown> | null;
  workflow?: { workflow_nodes: Record<string, WorkflowNode[]> } | null;
  exif?: Record<string, string> | null;
  raw_chunks?: Record<string, unknown> | null;
  raw_parameters?: string | null;
  raw_params?: string | null;
  folder_id?: number | null;
}

interface WorkflowNode {
  node_id: string;
  class_type: string;
  title?: string;
  inputs?: Record<string, unknown>;
}

interface FolderInfo {
  id: number;
  path: string;
  name: string;
  scanned_at?: string | null;
  created_at?: string | null;
  image_count: number;
}

interface Session {
  id: number;
  name: string;
  images: ImageListItem[];
  startIdx: number;
}

interface SavedSession {
  id: number;
  name: string;
  startIdx: number;
  imageCount: number;
}

interface AppState {
  folderId: number | null;
  page: number;
  activeIndex: number;
  viewMode: ViewMode;
  totalImages: number;
  allLoaded: boolean;
  folderName: string;
  sessions: SavedSession[];
  activeSessionId: number;
}

interface ScanResponse {
  folder_id: number;
  folder: FolderInfo | null;
  page: number;
  per_page: number;
  total: number;
  images: ImageListItem[];
  cached: number;
  processed: number;
  error?: string;
}

interface UploadResponse {
  images: Array<ImageDetail | { file: string; error: string }>;
  count: number;
  folder_id?: number;
}

interface ImagesResponse {
  images: ImageListItem[];
  total: number;
  page: number;
  per_page: number;
}

interface ImageDetailResponse extends ImageDetail {}

interface ExtractResponse {
  images: Array<ImageDetail | { file: string; error: string }>;
  count: number;
}

interface FolderListResponse {
  folders: FolderInfo[];
}
