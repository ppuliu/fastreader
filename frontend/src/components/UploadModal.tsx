import { useRef, useState } from 'react';
import { uploadDocument } from '../api';

export function UploadModal({ onClose, onStarted }:
  { onClose: () => void; onStarted: () => void }) {
  const [title, setTitle] = useState('');
  const [author, setAuthor] = useState('');
  const [kind, setKind] = useState<'book' | 'paper'>('book');
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const words = text.trim() ? text.trim().split(/\s+/).length : 0;

  const loadFile = (f: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      setText(String(reader.result ?? ''));
      if (!title) setTitle(f.name.replace(/\.(txt|md|markdown)$/i, ''));
    };
    reader.readAsText(f);
  };

  const submit = async () => {
    setError('');
    setBusy(true);
    try {
      await uploadDocument({ title: title.trim(), author: author.trim() || 'Unknown', kind, text });
      onStarted();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4 font-sans"
      onClick={onClose}>
      <div className="w-full max-w-xl rounded-2xl border border-[#2a2a36] bg-[#14141c] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-[#e6e7ee]">Add a document</h2>
        <p className="mt-1 text-[13px] text-[#8b8f9e]">
          Paste text or load a .txt / .md file. An agent rewrites it into zoom levels — this
          takes a few minutes for long documents.
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title"
            className="rounded-lg border border-[#2a2a36] bg-[#0d0e14] px-3 py-2 text-sm text-[#e6e7ee] outline-none focus:border-[#4a4d61]" />
          <input value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="Author (optional)"
            className="rounded-lg border border-[#2a2a36] bg-[#0d0e14] px-3 py-2 text-sm text-[#e6e7ee] outline-none focus:border-[#4a4d61]" />
          <select value={kind} onChange={(e) => setKind(e.target.value as 'book' | 'paper')}
            className="rounded-lg border border-[#2a2a36] bg-[#0d0e14] px-3 py-2 text-sm text-[#e6e7ee] outline-none">
            <option value="book">Book</option>
            <option value="paper">Paper</option>
          </select>
        </div>

        <textarea value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Paste the full document text here…"
          className="mt-3 h-52 w-full resize-none rounded-lg border border-[#2a2a36] bg-[#0d0e14] p-3 text-[13px] leading-relaxed text-[#d7d9e0] outline-none focus:border-[#4a4d61]" />

        <div className="mt-2 flex items-center justify-between text-[12px] text-[#6d6d7c]">
          <button onClick={() => fileRef.current?.click()}
            className="rounded-md border border-[#2a2a36] px-3 py-1.5 hover:border-[#4a4d61] hover:text-[#a5a8b5] cursor-pointer">
            Load .txt / .md file…
          </button>
          <span>{words.toLocaleString()} words {words > 0 && words < 120 && '· need ≥120'}</span>
          <input ref={fileRef} type="file" accept=".txt,.md,.markdown,text/plain" className="hidden"
            onChange={(e) => e.target.files?.[0] && loadFile(e.target.files[0])} />
        </div>

        {error && <div className="mt-3 rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-[13px] text-red-300">{error}</div>}

        <div className="mt-5 flex justify-end gap-3">
          <button onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-[#8b8f9e] hover:text-[#d7d9e0] cursor-pointer">Cancel</button>
          <button onClick={submit} disabled={busy || !title.trim() || words < 120}
            className="rounded-lg bg-[#d4b45a] px-4 py-2 text-sm font-medium text-[#14141c]
                       disabled:opacity-40 hover:bg-[#e0c26e] cursor-pointer">
            {busy ? 'Uploading…' : 'Process document'}
          </button>
        </div>
      </div>
    </div>
  );
}
