"use client";

import type { BusyAction, StyleProfile } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";
import { StyleProfileEditor } from "./StyleProfileEditor";

type EditStyleModalProps = {
  style: StyleProfile;
  styleName: string;
  profileJson: string;
  busyAction: BusyAction;
  editError: string;
  onNameChange: (value: string) => void;
  onProfileJsonChange: (value: string) => void;
  onSave: () => void;
  onClose: () => void;
};

export function EditStyleModal(props: EditStyleModalProps) {
  const {
    style,
    styleName,
    profileJson,
    busyAction,
    editError,
    onNameChange,
    onProfileJsonChange,
    onSave,
    onClose,
  } = props;

  const { requireAuth } = useAuth();
  const busy = busyAction === "edit_style";

  function handleClose() {
    if (busy) return;
    onClose();
  }

  return (
    <div className="modal-overlay">
      <div className="modal-dialog new-style-modal">
        <div className="modal-header">
          <h2 className="modal-title">编辑风格</h2>
          <button
            className="modal-close-btn"
            type="button"
            onClick={handleClose}
            disabled={busy}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div className="modal-step-content">
            <p className="form-hint" style={{ marginTop: 0 }}>
              修改风格名称或调整风格档案数据后保存。已生成文章不会受影响。
            </p>

            <StyleProfileEditor
              name={styleName}
              profileJson={profileJson}
              busy={busy}
              error={editError}
              saveLabel={busy ? "正在保存……" : "保存修改"}
              onNameChange={onNameChange}
              onProfileJsonChange={onProfileJsonChange}
              onSave={onSave}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
