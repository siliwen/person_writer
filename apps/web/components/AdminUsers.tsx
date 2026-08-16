"use client";

import { useCallback, useEffect, useState } from "react";
import {
  adjustAdminUserPoints,
  fetchAdminTiers,
  fetchAdminUsers,
  setAdminUserTier,
} from "@/lib/api";
import { useEscapeClose } from "@/lib/useEscapeClose";
import type { AdminTier, AdminUser } from "@/lib/types";

const PAGE_SIZE = 20;

export function AdminUsers() {
  const [q, setQ] = useState("");
  const [tier, setTier] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [tiers, setTiers] = useState<AdminTier[]>([]);
  const [selected, setSelected] = useState<AdminUser | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    fetchAdminUsers({ page, page_size: PAGE_SIZE, q: q || undefined, tier: tier || undefined })
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e) => setError(e.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [page, q, tier]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    fetchAdminTiers()
      .then((r) => setTiers(r.items))
      .catch(() => setTiers([]));
  }, []);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div className="settings-section-title">用户与账号</div>

      <div className="admin-filter-bar">
        <input
          className="form-input"
          placeholder="搜索用户名 / 昵称 / 邮箱"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setPage(1);
              load();
            }
          }}
        />
        <select className="form-select" value={tier} onChange={(e) => setTier(e.target.value)}>
          <option value="">全部等级</option>
          {tiers.map((t) => (
            <option key={t.code} value={t.code}>{t.name}</option>
          ))}
        </select>
        <button className="btn btn-primary btn-sm" type="button" onClick={() => { setPage(1); load(); }}>
          搜索
        </button>
      </div>

      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      {loading ? <p className="inline-status">加载中……</p> : null}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>昵称</th>
              <th>等级</th>
              <th>剩余积分</th>
              <th>注册时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading ? (
              <tr><td colSpan={6} className="admin-table-empty">没有匹配的用户</td></tr>
            ) : (
              items.map((u) => (
                <tr key={u.user_id}>
                  <td>{u.username}</td>
                  <td>{u.display_name}</td>
                  <td>{tiers.find((t) => t.code === u.tier_code)?.name ?? u.tier_code ?? "—"}</td>
                  <td>{u.points_balance}</td>
                  <td>{new Date(u.created_at).toLocaleString("zh-CN")}</td>
                  <td>
                    <button className="btn btn-ghost btn-sm" type="button" onClick={() => setSelected(u)}>
                      管理
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="admin-pagination">
        <button className="btn btn-ghost btn-sm" type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          上一页
        </button>
        <span className="admin-pagination-info">第 {page} / {totalPages} 页 · 共 {total} 人</span>
        <button className="btn btn-ghost btn-sm" type="button" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
          下一页
        </button>
      </div>

      {selected ? (
        <UserManageModal
          user={selected}
          tiers={tiers}
          onClose={() => setSelected(null)}
          onChanged={(updated) => {
            setItems((prev) => prev.map((u) => (u.user_id === updated.user_id ? updated : u)));
            // 同步弹窗内展示的等级/余额，避免操作后仍显示旧值
            setSelected(updated);
          }}
        />
      ) : null}
    </div>
  );
}

function UserManageModal({
  user,
  tiers,
  onClose,
  onChanged,
}: {
  user: AdminUser;
  tiers: AdminTier[];
  onClose: () => void;
  onChanged: (u: AdminUser) => void;
}) {
  const [delta, setDelta] = useState("");
  const [reason, setReason] = useState("");
  const [targetTier, setTargetTier] = useState(user.tier_code ?? "free");
  const [grantPoints, setGrantPoints] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  // 提交中不允许 ESC 关闭
  useEscapeClose(onClose, !busy);

  async function handleAdjust() {
    const d = parseInt(delta, 10);
    if (!Number.isFinite(d) || d === 0) {
      setError("请输入非零的积分数（正为增加，负为扣减）。");
      return;
    }
    if (!reason.trim()) {
      setError("请填写调整原因，该操作会记入审计日志。");
      return;
    }
    setBusy(true);
    setError("");
    setOkMsg("");
    try {
      const updated = await adjustAdminUserPoints(user.user_id, d, reason);
      onChanged(updated);
      setOkMsg(`已${d > 0 ? "增加" : "扣减"} ${Math.abs(d)} 积分。`);
      setDelta("");
    } catch (e) {
      setError((e as Error).message ?? "操作失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleSetTier() {
    if (!reason.trim()) {
      setError("请填写变更原因，该操作会记入审计日志。");
      return;
    }
    setBusy(true);
    setError("");
    setOkMsg("");
    try {
      const updated = await setAdminUserTier(user.user_id, targetTier ?? "free", grantPoints, reason);
      onChanged(updated);
      setOkMsg("已更新会员等级。");
    } catch (e) {
      setError((e as Error).message ?? "操作失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog admin-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">管理用户：{user.username}</div>
          <button className="modal-close" type="button" onClick={onClose} aria-label="关闭">×</button>
        </div>

        <div className="modal-body">
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          {okMsg ? <p className="inline-status admin-ok">{okMsg}</p> : null}

          <div className="admin-field-row">
            <span className="admin-field-label">当前等级</span>
            <span>{tiers.find((t) => t.code === user.tier_code)?.name ?? user.tier_code ?? "—"}</span>
          </div>
          <div className="admin-field-row">
            <span className="admin-field-label">剩余积分</span>
            <span>{user.points_balance}</span>
          </div>

          <div className="admin-form-stack">
            <label className="admin-form-label" htmlFor="admin-reason">
              操作原因<span className="admin-required">*</span>
            </label>
            <input
              id="admin-reason"
              className="form-input"
              placeholder="例如：客服补偿工单 #1234"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>

          <div className="settings-section-title">调整积分</div>
          <div className="admin-form-row">
            <input
              className="form-input"
              type="number"
              placeholder="积分增减（正为增加，负为扣减）"
              value={delta}
              onChange={(e) => setDelta(e.target.value)}
            />
            <button className="btn btn-primary btn-sm" type="button" disabled={busy} onClick={handleAdjust}>
              提交
            </button>
          </div>

          <div className="settings-section-title">调整会员等级</div>
          <div className="admin-form-row">
            <select className="form-select" value={targetTier ?? ""} onChange={(e) => setTargetTier(e.target.value)}>
              {tiers.map((t) => (
                <option key={t.code} value={t.code}>{t.name}</option>
              ))}
            </select>
            <label className="admin-checkbox">
              <input type="checkbox" checked={grantPoints} onChange={(e) => setGrantPoints(e.target.checked)} />
              补发该等级月额度
            </label>
            <button className="btn btn-primary btn-sm" type="button" disabled={busy} onClick={handleSetTier}>
              升级/降级
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
