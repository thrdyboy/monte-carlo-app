import { useEffect, useState } from "react";

export type ToastKind = "success" | "error" | "info";

export interface ToastMessage {
    id: number;
    kind: ToastKind;
    text: string;
}

let nextId = 1;

/** Small pub-sub so any component can push a toast without context. */
type Listener = (msgs: ToastMessage[]) => void;
const listeners = new Set<Listener>();
let messages: ToastMessage[] = [];

export function pushToast(kind: ToastKind, text: string) {
    const msg: ToastMessage = { id: nextId++, kind, text };
    messages = [...messages, msg];
    listeners.forEach((l) => l(messages));

    setTimeout(() => {
        messages = messages.filter((m) => m.id !== msg.id);
        listeners.forEach((l) => l(messages));
    }, 4500);
}

export function ToastHost() {
    const [items, setItems] = useState<ToastMessage[]>(messages);

    useEffect(() => {
        const listener: Listener = (msgs) => setItems([...msgs]);
        listeners.add(listener);
        return () => {
            listeners.delete(listener);
        };
    }, []);

    const colorFor = (kind: ToastKind) =>
        kind === "success"
            ? "bg-emerald-600"
            : kind === "error"
                ? "bg-rose-600"
                : "bg-slate-700";

    return (
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
            {items.map((m) => (
                <div
                    key={m.id}
                    className={`${colorFor(m.kind)} text-white text-sm px-4 py-3 rounded-lg shadow-lg max-w-md animate-in`}
                >
                    {m.text}
                </div>
            ))}
        </div>
    );
}