import { ArrowUp, File, Paperclip, X } from "@phosphor-icons/react";
import { useRef, useState } from "react";

interface Props {
  agentName: string;
  disabled: boolean;
  sending: boolean;
  onSend: (text: string, files: File[]) => Promise<boolean>;
}

export function Composer({ agentName, disabled, sending, onSend }: Props) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const appendFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    setFiles((current) => [...current, ...Array.from(incoming)]);
  };
  const submit = async () => {
    if (disabled || sending || (!text.trim() && !files.length)) return;
    const submittedText = text.trim();
    const submittedFiles = files;
    setText("");
    setFiles([]);
    const sent = await onSend(submittedText, submittedFiles);
    if (!sent) {
      setText((current) => current || submittedText);
      setFiles((current) => current.length ? current : submittedFiles);
    }
  };

  return (
    <div
      className={`composer-shell ${dragging ? "is-dragging" : ""}`}
      onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => { event.preventDefault(); setDragging(false); appendFiles(event.dataTransfer.files); }}
    >
      {files.length > 0 && <div className="file-queue">
        {files.map((file, index) => <div className="file-chip" key={`${file.name}-${index}`}><File size={18} /><span><strong>{file.name}</strong><small>{Math.max(1, Math.round(file.size / 1024))} KB</small></span><button onClick={() => setFiles((current) => current.filter((_, item) => item !== index))} aria-label={`Remover ${file.name}`}><X size={16} /></button></div>)}
      </div>}
      <div className="composer-row">
        <input ref={input} hidden type="file" multiple onChange={(event) => appendFiles(event.target.files)} />
        <button className="composer-tool" onClick={() => input.current?.click()} disabled={disabled || sending} aria-label="Anexar arquivos"><Paperclip size={23} /></button>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(); } }}
          placeholder={`Mensagem para ${agentName}`}
          aria-label={`Mensagem para ${agentName}`}
          rows={1}
          disabled={disabled}
        />
        <button className="send-button" onClick={() => void submit()} disabled={disabled || sending || (!text.trim() && !files.length)} aria-label="Enviar mensagem"><ArrowUp size={21} weight="bold" /></button>
      </div>
      {dragging && <div className="drop-hint">Solte os arquivos para anexar</div>}
    </div>
  );
}
