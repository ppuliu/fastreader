import { useEffect, useState } from 'react';
import { fetchDoc, fetchSummaries } from './api';
import type { DocSummary, FastDoc } from './lib/doc';
import { Library } from './components/Library';
import { Reader } from './components/Reader';

export default function App() {
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [open, setOpen] = useState<FastDoc | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { fetchSummaries().then(setDocs).catch((e) => setError(String(e))); }, []);
  if (error) return <div className="p-10 font-sans text-red-400">{error}</div>;
  if (open) return <Reader doc={open} onBack={() => setOpen(null)} />;
  return <Library docs={docs} onOpen={(id) => fetchDoc(id).then(setOpen).catch((e) => setError(String(e)))} />;
}
