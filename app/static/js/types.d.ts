type ViewMode = 'list' | 'grid' | 'gallery';

interface ImageListItem {
  id?: number;
  file_name: string;
  file?: string;
  path?: string;
  format?: string;
  size?: [number, number];
  mode?: string;
  error?: string | null;
  thumbnail?: string;
  width?: number;
  height?: number;
}

interface ImageDetail extends ImageListItem {
  prompt_parameters?: PromptParameters;
  workflow?: { workflow_nodes: Record<string, WorkflowNode[]> };
  exif?: Record<string, string>;
  raw_chunks?: Record<string, unknown>;
  raw_parameters?: string;
  folder_id?: number;
}

interface PromptParameters {
  positive_prompt?: string;
  negative_prompt?: string;
  generation_settings?: Record<string, unknown>;
  extra_settings?: Record<string, unknown>;
  [key: string]: unknown;
}

interface WorkflowNode {
  node_id: string;
  class_type: string;
  title?: string;
  inputs?: Record<string, unknown>;
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
  folder: { id: number; path: string; name: string } | null;
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
