import { CheckCircle2, AlertCircle, Info } from "lucide-react";

export interface ToastMessage {
  id: number;
  text: string;
  type: "info" | "success" | "error";
}

interface ToastStackProps {
  toasts: ToastMessage[];
  onDismiss: (id: number) => void;
}

export function ToastStack({ toasts, onDismiss }: ToastStackProps) {
  if (toasts.length === 0) return null;
  return (
    <div className="toast-stack">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`toast-item ${t.type}`}
          onClick={() => onDismiss(t.id)}
          role="status"
        >
          {t.type === "success" && <CheckCircle2 size={16} />}
          {t.type === "error" && <AlertCircle size={16} />}
          {t.type === "info" && <Info size={16} />}
          <span>{t.text}</span>
        </div>
      ))}
    </div>
  );
}
