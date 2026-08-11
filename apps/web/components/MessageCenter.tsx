"use client";

import { useEffect, useState } from "react";
import { fetchMyMessages, markAllMessagesRead, markMessageRead } from "@/lib/api";
import type { MessageInboxItem } from "@/lib/types";

type Props = {
  onClose: () => void;
  onUnreadChange?: (count: number) => void;
};

const PAGE_SIZE = 5;

export function MessageCenter({ onClose, onUnreadChange }: Props) {
  const [items, setItems] = useState<MessageInboxItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load(targetPage?: number) {
    setLoading(true);
    try {
      const p = targetPage ?? page;
      const res = await fetchMyMessages({ unread_only: unreadOnly, page: p, page_size: PAGE_SIZE });
      setItems(res.items);
      setTotal(res.total);
      setPage(res.page);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setPage(1);
    load(1);
    // 关闭弹窗时刷新未读数
    return () => {
      onUnreadChange?.(0);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unreadOnly]);

  useEffect(() => {
    if (page !== 1 || items.length > 0 || total > 0) {
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  async function handleRead(item: MessageInboxItem) {
    if (item.is_read) return;
    setBusy(true);
    try {
      await markMessageRead(item.id);
      setItems((prev) => prev.map((m) => (m.id === item.id ? { ...m, is_read: true, read_at: new Date().toISOString() } : m)));
      const left = items.filter((m) => !m.is_read && m.id !== item.id).length;
      onUnreadChange?.(left);
    } finally {
      setBusy(false);
    }
  }

  async function handleReadAll() {
    setBusy(true);
    try {
      await markAllMessagesRead();
      setItems((prev) => prev.map((m) => ({ ...m, is_read: true, read_at: new Date().toISOString() })));
      onUnreadChange?.(0);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card messages-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">
          消息中心
          <button type="button" className="modal-close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>
        <div className="messages-toolbar">
          <label className="admin-check">
            <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
            仅看未读
          </label>
          <button type="button" className="btn btn-ghost btn-sm" onClick={handleReadAll} disabled={busy}>
            全部已读
          </button>
        </div>
        <div className="messages-list">
          {loading ? <div className="admin-hint">加载中…</div> : null}
          {!loading && items.length === 0 ? <div className="admin-hint">暂无消息</div> : null}
          {items.map((m) => (
            <div
              key={m.id}
              className={`message-item ${m.is_read ? "" : "unread"} ${m.important ? "important" : ""}`}
              onClick={() => handleRead(m)}
            >
              <div className="message-item-head">
                {!m.is_read ? <span className="msg-dot" /> : null}
                {m.is_automated ? <span className="style-card-badge">系统</span> : null}
                {m.important ? <span className="style-card-badge important">重要</span> : null}
                <span className="message-item-title">{m.title}</span>
                {m.sent_at ? <span className="message-item-time">{new Date(m.sent_at).toLocaleString("zh-CN")}</span> : null}
              </div>
              <div className="message-item-body">{m.body}</div>
            </div>
          ))}
        </div>
        <MessagePagination page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />
      </div>
    </div>
  );
}

type PaginationProps = {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
};

function MessagePagination({ page, pageSize, total, onChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  return (
    <div className="messages-pagination">
      <button type="button" className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        上一页
      </button>
      <span className="messages-pagination-info">
        第 {page} / {totalPages} 页（共 {total} 条）
      </span>
      <button type="button" className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>
        下一页
      </button>
    </div>
  );
}
