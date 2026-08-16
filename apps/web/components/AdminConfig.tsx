"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createAdminBracket,
  createAdminModelPricing,
  createAdminOperationCost,
  createAdminTier,
  deleteAdminBracket,
  deleteAdminModelPricing,
  deleteAdminOperationCost,
  deleteAdminTier,
  fetchAdminBrackets,
  fetchAdminModelPricing,
  fetchAdminOperationCosts,
  fetchAdminTiers,
  updateAdminBracket,
  updateAdminModelPricing,
  updateAdminOperationCost,
  updateAdminTier,
} from "@/lib/api";
import { useEscapeClose } from "@/lib/useEscapeClose";

type FieldType = "text" | "number" | "checkbox" | "nullable-number";
type FieldDef = {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  readonlyOnEdit?: boolean;
};

type AnyItem = Record<string, any>;
type ConfigApi = {
  fetchList: () => Promise<{ items: AnyItem[] }>;
  create: (payload: AnyItem) => Promise<AnyItem>;
  update: (id: string, payload: AnyItem) => Promise<AnyItem>;
  remove: (id: string) => Promise<AnyItem>;
};

const tierFields: FieldDef[] = [
  { key: "code", label: "等级 code", type: "text", required: true, readonlyOnEdit: true },
  { key: "name", label: "名称", type: "text", required: true },
  { key: "monthly_points", label: "每月积分", type: "number", required: true },
  { key: "price_monthly", label: "月费(分)", type: "number", required: true },
  { key: "style_limit", label: "风格上限(0不限)", type: "number" },
  { key: "material_limit", label: "素材上限(0不限)", type: "number" },
  { key: "max_article_length", label: "单篇字数上限(0不限)", type: "number" },
  { key: "sort_order", label: "排序", type: "number" },
  { key: "can_download", label: "可下载", type: "checkbox" },
  { key: "can_rewrite", label: "可重写", type: "checkbox" },
  { key: "is_active", label: "启用", type: "checkbox" },
];

const bracketFields: FieldDef[] = [
  { key: "id", label: "档位 id", type: "text", required: true, readonlyOnEdit: true },
  { key: "label", label: "档位名", type: "text", required: true },
  { key: "min_length", label: "最小字数", type: "number", required: true },
  { key: "max_length", label: "最大字数(空=不限)", type: "nullable-number" },
  { key: "sort_order", label: "排序", type: "number" },
  { key: "is_active", label: "启用", type: "checkbox" },
];

const opcostFields: FieldDef[] = [
  { key: "id", label: "操作 id", type: "text", required: true, readonlyOnEdit: true },
  { key: "op_type", label: "操作类型", type: "text", required: true },
  { key: "points", label: "积分", type: "number", required: true },
  { key: "description", label: "说明", type: "text" },
  { key: "is_active", label: "启用", type: "checkbox" },
];

const pricingFields: FieldDef[] = [
  { key: "id", label: "单价 id", type: "text", required: true, readonlyOnEdit: true },
  { key: "model", label: "模型名", type: "text", required: true },
  { key: "input_price_per_m", label: "输入价(¥/百万)", type: "number", required: true },
  { key: "output_price_per_m", label: "输出价(¥/百万)", type: "number", required: true },
  { key: "currency", label: "币种", type: "text" },
  { key: "note", label: "备注", type: "text" },
  { key: "is_active", label: "启用", type: "checkbox" },
];

const configTabs: Array<{
  key: string;
  label: string;
  fields: FieldDef[];
  idKey: string;
  api: ConfigApi;
}> = [
  { key: "tiers", label: "会员等级", fields: tierFields, idKey: "code", api: {
    fetchList: fetchAdminTiers, create: createAdminTier as any, update: updateAdminTier as any, remove: deleteAdminTier as any,
  } },
  { key: "brackets", label: "长度档位", fields: bracketFields, idKey: "id", api: {
    fetchList: fetchAdminBrackets, create: createAdminBracket as any, update: updateAdminBracket as any, remove: deleteAdminBracket as any,
  } },
  { key: "opcosts", label: "操作积分", fields: opcostFields, idKey: "id", api: {
    fetchList: fetchAdminOperationCosts, create: createAdminOperationCost as any, update: updateAdminOperationCost as any, remove: deleteAdminOperationCost as any,
  } },
  { key: "pricing", label: "模型单价", fields: pricingFields, idKey: "id", api: {
    fetchList: fetchAdminModelPricing, create: createAdminModelPricing as any, update: updateAdminModelPricing as any, remove: deleteAdminModelPricing as any,
  } },
];

function emptyFromFields(fields: FieldDef[]): AnyItem {
  const obj: AnyItem = {};
  for (const f of fields) {
    if (f.type === "checkbox") obj[f.key] = false;
    else if (f.type === "number") obj[f.key] = 0;
    else if (f.type === "nullable-number") obj[f.key] = "";
    else obj[f.key] = "";
  }
  return obj;
}

function buildPayload(fields: FieldDef[], form: AnyItem): AnyItem {
  const payload: AnyItem = {};
  for (const f of fields) {
    const v = form[f.key];
    if (f.type === "checkbox") payload[f.key] = Boolean(v);
    else if (f.type === "number") payload[f.key] = v === "" || v == null ? 0 : Number(v);
    else if (f.type === "nullable-number") payload[f.key] = v === "" || v == null ? null : Number(v);
    else payload[f.key] = v ?? "";
  }
  return payload;
}

export function AdminConfig() {
  const [tabKey, setTabKey] = useState(configTabs[0].key);
  const tab = configTabs.find((t) => t.key === tabKey)!;

  return (
    <div>
      <div className="settings-section-title">会员与配置</div>
      <div className="admin-subnav admin-subnav-compact">
        {configTabs.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`admin-subnav-item ${tabKey === t.key ? "active" : ""}`}
            onClick={() => setTabKey(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <ConfigManager key={tab.key} fields={tab.fields} idKey={tab.idKey} api={tab.api} title={tab.label} />
    </div>
  );
}

function ConfigManager({
  fields,
  idKey,
  api,
  title,
}: {
  fields: FieldDef[];
  idKey: string;
  api: ConfigApi;
  title: string;
}) {
  const [items, setItems] = useState<AnyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<AnyItem | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    api.fetchList()
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  /** 保存。失败时抛出，由弹窗就地展示错误（弹窗遮住了列表区的错误条）。 */
  async function handleSave(form: AnyItem) {
    const payload = buildPayload(fields, form);
    const id = String(form[idKey] ?? "");
    // 关键：用「主键是否已存在于列表」判断新增 or 编辑。
    // 不能用 editing 是否为真——新增时 editing 也是一个空表单对象。
    const isEdit = items.some((it) => String(it[idKey]) === id);
    if (isEdit) {
      await api.update(id, payload);
    } else {
      await api.create(payload);
    }
    setError("");
    setEditing(null);
    load();
  }

  async function handleDelete(item: AnyItem) {
    if (!window.confirm(`确认删除「${item[idKey]}」？此操作会记入审计。`)) return;
    try {
      await api.remove(item[idKey]);
      load();
    } catch (e) {
      setError((e as Error).message ?? "删除失败");
    }
  }

  return (
    <div>
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      <div className="admin-action-bar">
        <button className="btn btn-primary btn-sm" type="button" onClick={() => setEditing(emptyFromFields(fields))}>
          新增{title}
        </button>
      </div>

      {loading ? <p className="inline-status">加载中……</p> : null}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              {fields.map((f) => (
                <th key={f.key}>{f.label}</th>
              ))}
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading ? (
              <tr><td colSpan={fields.length + 1} className="admin-table-empty">暂无数据</td></tr>
            ) : (
              items.map((it) => (
                <tr key={it[idKey]}>
                  {fields.map((f) => (
                    <td key={f.key}>
                      {f.type === "checkbox"
                        ? it[f.key]
                          ? "是"
                          : "否"
                        : it[f.key] === null || it[f.key] === undefined
                        ? "—"
                        : String(it[f.key])}
                    </td>
                  ))}
                  <td className="admin-table-actions">
                    <button className="admin-action-text" type="button" onClick={() => setEditing({ ...it })}>编辑</button>
                    <span className="admin-action-divider" aria-hidden="true">|</span>
                    <button className="admin-action-text admin-action-danger" type="button" onClick={() => handleDelete(it)}>删除</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {editing ? (
        <ConfigFormModal
          fields={fields}
          idKey={idKey}
          title={title}
          initial={editing}
          onClose={() => setEditing(null)}
          onSave={handleSave}
        />
      ) : null}
    </div>
  );
}

function ConfigFormModal({
  fields,
  idKey,
  title,
  initial,
  onClose,
  onSave,
}: {
  fields: FieldDef[];
  idKey: string;
  title: string;
  initial: AnyItem;
  onClose: () => void;
  onSave: (form: AnyItem) => Promise<void>;
}) {
  const [form, setForm] = useState<AnyItem>(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isEdit = Boolean(initial[idKey]);

  // 保存中不允许 ESC 关闭
  useEscapeClose(onClose, !busy);

  function setField(key: string, value: any) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit() {
    const missing = fields
      .filter((f) => f.required && f.type !== "checkbox")
      .filter((f) => {
        const v = form[f.key];
        return v === "" || v === null || v === undefined;
      });
    if (missing.length > 0) {
      setError(`请填写必填项：${missing.map((f) => f.label).join("、")}`);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onSave(form);
    } catch (e) {
      setError((e as Error).message ?? "保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog admin-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">{isEdit ? `编辑${title}` : `新增${title}`}</div>
          <button className="modal-close" type="button" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="modal-body">
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <div className="admin-form-grid">
            {fields.map((f) => (
              <label key={f.key} className="admin-form-field">
                <span className="admin-form-label">
                  {f.label}
                  {f.required ? <span className="admin-required">*</span> : null}
                  {f.readonlyOnEdit && isEdit ? <span className="admin-readonly-tag">不可改</span> : null}
                </span>
                {f.type === "checkbox" ? (
                  <input
                    type="checkbox"
                    checked={Boolean(form[f.key])}
                    onChange={(e) => setField(f.key, e.target.checked)}
                  />
                ) : (
                  <input
                    className="form-input"
                    type={f.type === "number" || f.type === "nullable-number" ? "number" : "text"}
                    value={form[f.key] ?? ""}
                    disabled={f.readonlyOnEdit && isEdit}
                    onChange={(e) => setField(f.key, e.target.value)}
                  />
                )}
              </label>
            ))}
          </div>
          <div className="admin-modal-actions">
            <button className="btn btn-ghost btn-sm" type="button" onClick={onClose} disabled={busy}>取消</button>
            <button className="btn btn-primary btn-sm" type="button" onClick={handleSubmit} disabled={busy}>
              {busy ? "保存中……" : "保存"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
