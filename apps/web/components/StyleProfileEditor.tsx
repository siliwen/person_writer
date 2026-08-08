"use client";

type StyleProfileEditorProps = {
  name: string;
  profileJson: string;
  busy?: boolean;
  disabled?: boolean;
  error?: string;
  saveLabel?: string;
  onNameChange: (value: string) => void;
  onProfileJsonChange: (value: string) => void;
  onSave: () => void;
};

export function StyleProfileEditor(props: StyleProfileEditorProps) {
  const {
    name,
    profileJson,
    busy,
    disabled,
    error,
    saveLabel,
    onNameChange,
    onProfileJsonChange,
    onSave,
  } = props;

  return (
    <div className="diag-confirm-section">
      <div className="form-field">
        <label className="form-label">风格名称</label>
        <input
          className="form-input"
          value={name}
          disabled={Boolean(disabled)}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="给这个风格起个名字"
        />
      </div>

      <details className="advanced-json">
        <summary>高级：查看和编辑完整风格档案数据</summary>
        <div className="form-field">
          <label className="form-label">风格分析结果（确认前可编辑）</label>
          <textarea
            className="form-textarea profile-json"
            value={profileJson}
            disabled={Boolean(disabled)}
            onChange={(e) => onProfileJsonChange(e.target.value)}
          />
        </div>
      </details>

      <button
        className="btn btn-primary"
        type="button"
        disabled={Boolean(busy) || Boolean(disabled)}
        onClick={onSave}
        style={{ width: "100%" }}
      >
        {saveLabel ?? "保存"}
      </button>

      {error ? <p className="inline-error" role="alert">{error}</p> : null}
    </div>
  );
}
