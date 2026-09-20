"use client";

import { useEffect, useRef } from "react";
import styles from "./ConfirmSurface.module.css";

type Props = {
  open: boolean;
  title: string;
  description: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmSurface({ open, title, description, onConfirm, onCancel }: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) cancelRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div className={styles.overlay} role="presentation">
      <div className={styles.surface} role="alertdialog" aria-modal="true" aria-label={title}>
        <h2 className={styles.title}>{title}</h2>
        <p className={styles.description}>{description}</p>
        <div className={styles.actions}>
          <button ref={cancelRef} type="button" className={styles.button} onClick={onCancel}>
            Keep booking
          </button>
          <button type="button" className={styles.destructive} onClick={onConfirm}>
            Cancel booking
          </button>
        </div>
      </div>
    </div>
  );
}
