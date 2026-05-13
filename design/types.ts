export interface SourceData {
  i: number;
  file: string;
  page: number;
  loc: string;
  excerpt: string;
}

export interface ChatSession {
  t: string;
  time: string;
  active: boolean;
  count: number;
  tag: string;
}

export interface NavItem {
  id: string;
  label: string;
  icon: string;
}
