export type PatchSource = 'ai' | 'user';

export interface SetOp {
  type: 'set';
  block_id: string;
  path: string;
  value: string;
  source: PatchSource;
}

export interface AppendOp {
  type: 'append';
  block_id: string;
  path: string;
  value: string;
  source: PatchSource;
}

export interface RemoveAtOp {
  type: 'remove_at';
  block_id: string;
  path: string;
  index: number;
  source: PatchSource;
}

export interface SetAtOp {
  type: 'set_at';
  block_id: string;
  path: string;
  index: number;
  value: string;
  source: PatchSource;
}

export type PatchOp = SetOp | AppendOp | RemoveAtOp | SetAtOp;
