export interface TreeNode {
  title: string;
  node_id: string;
  start_index: number;
  end_index: number;
  summary: string;
  body?: string | null;
  nodes?: TreeNode[];
}

export interface BookData {
  doc_name: string;
  book_slug: string;
  doc_description: string;
  source_url: string;
  source_authority: string;
  source_publisher: string;
  language: string;
  subject: string;
  subject_scope: "rajasthan" | "pan_india" | "world";
  exam_coverage: string[];
  ingested_at: string;
  cleaned_at: string;
  cleanup_version: string;
  cleaner_layers_applied: string[];
  pageindex_version: string;
  llm_model_indexing: string;
  structure: TreeNode[];
}

export interface ManifestEntry {
  slug: string;
  name: string;
  scope: string;
  file?: string;
  skill_folder?: string;
}

export interface TreeStats {
  totalNodes: number;
  maxDepth: number;
  pageRange: [number, number];
}

export interface NodeWithPath {
  node: TreeNode;
  path: TreeNode[];
}
