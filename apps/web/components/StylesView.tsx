"use client";

import type { BusyAction, StyleProfile } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

type StylesViewProps = {
  styles: StyleProfile[];
  selectedStyleId: string;
  busyAction: BusyAction;
  deleteStyleError: string;
  onStartWriting: (styleId: string) => void;
  onDeleteStyle: (styleId: string) => void;
  onNewStyle: () => void;
  onEditStyle: (styleId: string) => void;
  onSetDefaultStyle: (styleId: string) => void;
};

const recommendedStyles = [
  { name: "鲁迅", surname: "鲁", keywords: ["锋利冷峻", "讽刺深刻"], color: "#C0392B" },
  { name: "茅盾", surname: "茅", keywords: ["宏大叙事", "社会写实"], color: "#5D6D7E" },
  { name: "沈从文", surname: "沈", keywords: ["诗意抒情", "田园牧歌"], color: "#1ABC9C" },
  { name: "张爱玲", surname: "张", keywords: ["华丽苍凉", "都市情感"], color: "#E74C8E" },
  { name: "余华", surname: "余", keywords: ["冷静克制", "苦难叙事"], color: "#2C3E50" },
  { name: "史铁生", surname: "史", keywords: ["沉思内省", "生命感悟"], color: "#E67E22" },
];

const barColors = ["", "teal", "amber"];

export function StylesView(props: StylesViewProps) {
  const {
    styles,
    busyAction,
    deleteStyleError,
    onStartWriting,
    onDeleteStyle,
    onNewStyle,
    onEditStyle,
    onSetDefaultStyle,
  } = props;

  const { requireAuth } = useAuth();

  const isDeleting = busyAction === "delete_style";
  const isBusy = busyAction === "edit_style" || busyAction === "set_default";

  function handleNewStyle() {
    if (!requireAuth()) return;
    onNewStyle();
  }

  function handleStartWriting(styleId: string) {
    if (!requireAuth()) return;
    onStartWriting(styleId);
  }

  function handleDelete(styleId: string) {
    onDeleteStyle(styleId);
  }

  function handleEdit(styleId: string) {
    if (!requireAuth()) return;
    onEditStyle(styleId);
  }

  function handleSetDefault(styleId: string) {
    if (!requireAuth()) return;
    onSetDefaultStyle(styleId);
  }

  return (
    <div>
      {/* My Styles section */}
      <div className="styles-section">
        <div className="styles-section-header">
          <h2 className="styles-section-title">
            我的风格
            <span className="styles-section-count">· {styles.length} 个</span>
          </h2>
        </div>

        {styles.length === 0 ? (
          <div
            className="empty-style-card"
            onClick={handleNewStyle}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleNewStyle();
              }
            }}
          >
            <div className="empty-style-card-icon">+</div>
            <div className="empty-style-card-title">创建你的第一个风格</div>
            <div className="empty-style-card-desc">
              上传你的作品，系统会自动分析你的写作风格并生成风格档案
            </div>
          </div>
        ) : (
          <div className="style-card-grid">
            {styles.map((style, idx) => (
              <div key={style.id} className="style-card style-card-clickable">
                <div className={`style-card-bar ${barColors[idx % 3]}`} />
                <div className="style-card-body">
                  <div
                    className="style-card-main"
                    onClick={() => handleStartWriting(style.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleStartWriting(style.id);
                      }
                    }}
                  >
                    <div className="style-card-header">
                      <span className="style-card-name">{style.name}</span>
                      {style.is_default ? <span className="style-card-badge default">默认</span> : null}
                    </div>
                    <div className="style-card-desc">
                      {style.status === "active" ? "点击开始写作" : style.status}
                    </div>
                    <div className="style-card-stats">
                      <span>状态 <strong>{style.status === "active" ? "可用" : style.status}</strong></span>
                    </div>
                    <div className="style-card-cta">
                      开始写作 →
                    </div>
                  </div>
                  <div className="style-card-actions">
                    <button
                      className="btn btn-ghost btn-sm"
                      type="button"
                      disabled={isBusy}
                      onClick={() => handleEdit(style.id)}
                    >
                      编辑
                    </button>
                    {!style.is_default ? (
                      <button
                        className="btn btn-ghost btn-sm"
                        type="button"
                        disabled={isBusy}
                        onClick={() => handleSetDefault(style.id)}
                      >
                        设为默认
                      </button>
                    ) : null}
                    <button
                      className="btn btn-ghost btn-sm"
                      type="button"
                      disabled={isDeleting}
                      onClick={() => handleDelete(style.id)}
                    >
                      {isDeleting ? "删除中……" : "删除"}
                    </button>
                  </div>
                </div>
              </div>
            ))}

            {/* Add new style card */}
            <div
              className="style-card style-card-add"
              onClick={handleNewStyle}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleNewStyle();
                }
              }}
            >
              <div className="style-card-add-icon">+</div>
              <div className="style-card-add-text">新建风格</div>
            </div>
          </div>
        )}
        {deleteStyleError ? <p className="inline-error" role="alert" style={{ marginTop: "12px" }}>{deleteStyleError}</p> : null}
      </div>

      {/* Recommended Styles section */}
      <div className="styles-section" style={{ marginTop: "32px" }}>
        <div className="styles-section-header">
          <h2 className="styles-section-title">推荐风格</h2>
          <span className="styles-section-badge">即将上线</span>
        </div>
        <p className="styles-section-hint">
          以下名家风格档案正在准备中，上线后可直接引用进行写作
        </p>
        <div className="recommended-grid">
          {recommendedStyles.map((rec) => (
            <div key={rec.name} className="recommended-card">
              <div
                className="recommended-avatar"
                style={{ backgroundColor: rec.color }}
              >
                {rec.surname}
              </div>
              <div className="recommended-name">{rec.name}</div>
              <div className="recommended-keywords">
                {rec.keywords.map((kw) => (
                  <span key={kw} className="recommended-keyword">{kw}</span>
                ))}
              </div>
              <div className="recommended-soon">即将上线</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
