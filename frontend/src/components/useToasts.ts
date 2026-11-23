import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react';

/** Un aviso flotante. Los de error no se cierran solos: hay que leerlos. */
export interface Toast {
  id: number;
  color: 'teal' | 'red' | 'orange';
  title: ReactNode;
  message?: ReactNode;
}

/** Segundos que dura un aviso que no es de error. */
const AUTO_CLOSE_MS = 8_000;

/**
 * Avisos flotantes de una página (2.2): `push` añade uno y `dismiss` lo quita. Sin dependencias nuevas: el pintado lo
 * hace `ToastStack`.
 */
export function useToasts() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = next.current++;
      setToasts((current) => [...current, { ...toast, id }]);
      if (toast.color !== 'red') {
        timers.current.set(
          id,
          setTimeout(() => dismiss(id), AUTO_CLOSE_MS),
        );
      }
      return id;
    },
    [dismiss],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach((timer) => clearTimeout(timer));
  }, []);

  return { toasts, push, dismiss };
}
