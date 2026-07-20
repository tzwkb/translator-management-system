"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { canPerform } from "../lib/roles";
import { calculateAmountCents, formatCurrency, formatRate, parseRateMicros } from "../lib/money";
import { formatApprovalSummary } from "../lib/approval-display";
import type {
  DemoRole,
  PoStatus,
  PurchaseOrder,
  Rate,
  Translator,
  WorkspaceData,
} from "../lib/types";

type View = "overview" | "translators" | "rates" | "pos" | "approvals";

const emptyWorkspace: WorkspaceData = {
  translators: [],
  rates: [],
  purchaseOrders: [],
  approvals: [],
  metrics: {
    translatorCount: 0,
    languagePairCount: 0,
    pendingAmounts: [],
    pendingApprovalCount: 0,
  },
};

const views: Array<{ id: View; label: string; mark: string }> = [
  { id: "overview", label: "总览", mark: "·" },
  { id: "translators", label: "译员", mark: "人" },
  { id: "rates", label: "费率", mark: "率" },
  { id: "pos", label: "PO", mark: "单" },
  { id: "approvals", label: "审核", mark: "审" },
];

const roleLabels: Record<DemoRole, string> = {
  boss: "Boss · 全部与审批",
  editor: "Editor · 业务编辑",
  viewer: "Viewer · 只读",
  agent: "Agent · 提案",
};

function translatorName(translators: Translator[], id: string): string {
  return translators.find((item) => item.id === id)?.name ?? "未找到译员";
}

export function LinguaControlWorkbench() {
  const [view, setView] = useState<View>("overview");
  const [role, setRole] = useState<DemoRole>("boss");
  const [workspace, setWorkspace] = useState<WorkspaceData>(emptyWorkspace);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [search, setSearch] = useState("");
  const [translatorFormOpen, setTranslatorFormOpen] = useState(false);
  const [editingTranslatorId, setEditingTranslatorId] = useState<string | null>(null);
  const [translatorForm, setTranslatorForm] = useState({
    name: "",
    email: "",
    nativeLanguage: "简体中文",
    status: "active",
    onboardedAt: "",
  });
  const [rateForm, setRateForm] = useState({
    translatorId: "",
    languagePair: "en-US → zh-CN",
    rate: "0.12",
    currency: "CNY",
  });
  const [poForm, setPoForm] = useState({
    poNumber: "",
    translatorId: "",
    month: "",
    languagePair: "en-US → zh-CN",
    wordCount: "",
    unitRate: "0.12",
    currency: "CNY",
    status: "draft" as PoStatus,
  });

  const canWrite = canPerform(role, "write-business");
  const canSubmit = canPerform(role, "submit-approval");
  const canReview = canPerform(role, "review-approval");

  const loadWorkspaceData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/workspace", { cache: "no-store" });
      const payload = (await response.json()) as WorkspaceData & { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "工作台数据加载失败");
      setWorkspace(payload);
      setRateForm((current) => ({
        ...current,
        translatorId: current.translatorId || payload.translators[0]?.id || "",
      }));
      setPoForm((current) => ({
        ...current,
        translatorId: current.translatorId || payload.translators[0]?.id || "",
      }));
    } catch (error) {
      setFeedback({ type: "error", text: error instanceof Error ? error.message : "加载失败" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => void loadWorkspaceData(), 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadWorkspaceData]);

  async function mutate(path: string, method: "POST" | "PATCH", body: unknown, success: string): Promise<boolean> {
    setBusy(true);
    setFeedback(null);
    try {
      const response = await fetch(path, {
        method,
        headers: { "content-type": "application/json", "x-demo-role": role },
        body: JSON.stringify(body),
      });
      const payload = (await response.json()) as { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "操作失败");
      await loadWorkspaceData();
      setFeedback({ type: "success", text: success });
      return true;
    } catch (error) {
      setFeedback({ type: "error", text: error instanceof Error ? error.message : "操作失败" });
      return false;
    } finally {
      setBusy(false);
    }
  }

  const visibleTranslators = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return workspace.translators;
    return workspace.translators.filter((item) =>
      [item.name, item.email, item.nativeLanguage].some((value) => value.toLowerCase().includes(keyword)),
    );
  }, [search, workspace.translators]);

  function openTranslatorForm(translator?: Translator) {
    if (translator) {
      setEditingTranslatorId(translator.id);
      setTranslatorForm({
        name: translator.name,
        email: translator.email,
        nativeLanguage: translator.nativeLanguage,
        status: translator.status,
        onboardedAt: translator.onboardedAt,
      });
    } else {
      setEditingTranslatorId(null);
      setTranslatorForm({ name: "", email: "", nativeLanguage: "简体中文", status: "active", onboardedAt: "" });
    }
    setTranslatorFormOpen(true);
  }

  async function saveTranslator(event: FormEvent) {
    event.preventDefault();
    const path = editingTranslatorId ? `/api/translators/${editingTranslatorId}` : "/api/translators";
    const saved = await mutate(path, editingTranslatorId ? "PATCH" : "POST", translatorForm, editingTranslatorId ? "译员资料已更新" : "译员已新增");
    if (saved) setTranslatorFormOpen(false);
  }

  async function saveRate(event: FormEvent) {
    event.preventDefault();
    const payload = {
      translatorId: rateForm.translatorId,
      languagePair: rateForm.languagePair,
      rateMicros: parseRateMicros(rateForm.rate),
      currency: rateForm.currency,
    };
    if (role === "agent") {
      await mutate("/api/approvals", "POST", { kind: "rate", payload, submittedBy: "Demo Agent（示例）" }, "费率提案已提交待审");
      return;
    }
    await mutate("/api/rates", "POST", payload, "费率已保存");
  }

  async function savePo(event: FormEvent) {
    event.preventDefault();
    const payload = {
      poNumber: poForm.poNumber,
      translatorId: poForm.translatorId,
      month: poForm.month,
      languagePair: poForm.languagePair,
      wordCount: Number(poForm.wordCount),
      unitRateMicros: parseRateMicros(poForm.unitRate),
      currency: poForm.currency,
      status: poForm.status,
    };
    if (role === "agent") {
      await mutate("/api/approvals", "POST", { kind: "po", payload, submittedBy: "Demo Agent（示例）" }, "PO 提案已提交待审");
      return;
    }
    await mutate("/api/pos", "POST", payload, "PO 已新增");
  }

  async function exportWorkbook() {
    setBusy(true);
    setFeedback(null);
    try {
      const response = await fetch("/api/export", { headers: { "x-demo-role": role } });
      if (!response.ok) {
        const payload = (await response.json()) as { error?: string };
        throw new Error(payload.error ?? "导出失败");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "lingua-control-demo.xlsx";
      link.click();
      URL.revokeObjectURL(url);
      setFeedback({ type: "success", text: "Excel 已导出" });
    } catch (error) {
      setFeedback({ type: "error", text: error instanceof Error ? error.message : "导出失败" });
    } finally {
      setBusy(false);
    }
  }

  const pendingApprovals = workspace.approvals.filter((item) => item.status === "pending");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-kicker">LANGLOBAL / OPS</span>
          <strong>Lingua<br />Control</strong>
          <span className="brand-cn">译员运营台</span>
        </div>

        <div className="language-track" aria-label="语言流转轨迹">
          <span>EN</span><i aria-hidden="true" /><span>ZH</span><i aria-hidden="true" /><span>JA</span>
        </div>

        <nav aria-label="主导航">
          {views.map((item) => (
            <button
              key={item.id}
              className={view === item.id ? "nav-item active" : "nav-item"}
              onClick={() => setView(item.id)}
              aria-current={view === item.id ? "page" : undefined}
            >
              <span aria-hidden="true">{item.mark}</span>{item.label}
              {item.id === "approvals" && pendingApprovals.length > 0 ? <b>{pendingApprovals.length}</b> : null}
            </button>
          ))}
        </nav>

        <div className="demo-stamp">
          <strong>受控 Demo</strong>
          <span>角色头仅用于演示，不是生产身份认证。</span>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">2026 / 业务运营切面</p>
            <h1>{views.find((item) => item.id === view)?.label}</h1>
          </div>
          <div className="topbar-actions">
            <label className="role-picker">
              <span>Demo 角色</span>
              <select value={role} onChange={(event) => setRole(event.target.value as DemoRole)} aria-describedby="role-warning">
                {Object.entries(roleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <button className="secondary-button" onClick={() => void exportWorkbook()} disabled={busy || loading}>Export .xlsx</button>
          </div>
        </header>

        <p id="role-warning" className="role-warning">⚠ 免密码角色切换仅供 owner-only 私有演示；服务端仍按当前角色拒绝越权写入。</p>

        {feedback ? <div className={`feedback ${feedback.type}`} role={feedback.type === "error" ? "alert" : "status"}>{feedback.text}</div> : null}
        {loading ? <div className="loading-state" role="status"><span />正在从 D1 读取演示数据…</div> : null}

        {!loading && view === "overview" ? (
          <section className="overview-grid" aria-label="运营总览">
            <article className="hero-panel">
              <p className="eyebrow">今日工作面</p>
              <h2>让每一笔语言交付，<br />都有费率和审核可追溯。</h2>
              <p>译员建档、报价、PO 与待审提案在同一工作面流转。当前数据均为明确标记的示例。</p>
              <button className="primary-button" onClick={() => setView(pendingApprovals.length ? "approvals" : "translators")}>
                {pendingApprovals.length ? `处理 ${pendingApprovals.length} 条待审` : "查看译员名录"}
              </button>
            </article>
            <div className="metric-ledger">
              <Metric label="在册译员" value={String(workspace.metrics.translatorCount).padStart(2, "0")} note="含停用的示例档案" />
              <Metric label="语言对" value={String(workspace.metrics.languagePairCount).padStart(2, "0")} note="按当前费率表去重" />
              <Metric label="待付金额" value={workspace.metrics.pendingAmounts.map((item) => formatCurrency(item.amountCents, item.currency)).join(" / ") || "—"} note="按币种分列，不含已付 PO" compact />
              <Metric label="待审核" value={String(workspace.metrics.pendingApprovalCount).padStart(2, "0")} note="仅 pending 状态" />
            </div>
            <article className="queue-panel">
              <div className="section-heading"><div><p className="eyebrow">流转队列</p><h2>待审摘要</h2></div><button className="text-button" onClick={() => setView("approvals")}>打开审核</button></div>
              {pendingApprovals.length ? pendingApprovals.slice(0, 3).map((approval) => (
                <div className="queue-row" key={approval.id}><span className="kind-tag">{approval.kind === "rate" ? "费率" : "PO"}</span><div><strong>{formatApprovalSummary(approval, workspace.translators)}</strong><span>{approval.submittedBy} · {approval.createdAt.slice(0, 10)}</span></div></div>
              )) : <EmptyState text="目前没有待审项，业务流转已清空。" />}
            </article>
          </section>
        ) : null}

        {!loading && view === "translators" ? (
          <section className="content-panel">
            <div className="section-heading"><div><p className="eyebrow">人才档案</p><h2>译员名录</h2></div><button className="primary-button" onClick={() => openTranslatorForm()} disabled={!canWrite || busy} title={!canWrite ? "当前角色只能查看" : undefined}>新增译员</button></div>
            <label className="search-field"><span>搜索译员</span><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="姓名、邮箱或母语" /></label>
            {translatorFormOpen ? (
              <form className="form-panel" onSubmit={(event) => void saveTranslator(event)}>
                <div className="form-title"><strong>{editingTranslatorId ? "编辑译员" : "新增译员"}</strong><button type="button" className="text-button" onClick={() => setTranslatorFormOpen(false)}>取消</button></div>
                <div className="form-grid">
                  <Field label="姓名"><input required value={translatorForm.name} onChange={(event) => setTranslatorForm({ ...translatorForm, name: event.target.value })} /></Field>
                  <Field label="邮箱"><input required type="email" value={translatorForm.email} onChange={(event) => setTranslatorForm({ ...translatorForm, email: event.target.value })} /></Field>
                  <Field label="母语"><input required value={translatorForm.nativeLanguage} onChange={(event) => setTranslatorForm({ ...translatorForm, nativeLanguage: event.target.value })} /></Field>
                  <Field label="状态"><select value={translatorForm.status} onChange={(event) => setTranslatorForm({ ...translatorForm, status: event.target.value })}><option value="active">在库</option><option value="inactive">停用</option></select></Field>
                  <Field label="入库日期"><input required type="date" value={translatorForm.onboardedAt} onChange={(event) => setTranslatorForm({ ...translatorForm, onboardedAt: event.target.value })} /></Field>
                </div>
                <button className="primary-button" disabled={busy}>{busy ? "正在保存…" : "保存译员"}</button>
              </form>
            ) : null}
            <DataTable columns={["姓名", "邮箱", "母语", "状态", "入库", ""]} empty={visibleTranslators.length === 0}>
              {visibleTranslators.map((translator) => <tr key={translator.id}><td><strong>{translator.name}</strong></td><td>{translator.email}</td><td>{translator.nativeLanguage}</td><td><StatusTag status={translator.status} /></td><td>{translator.onboardedAt}</td><td><button className="text-button" onClick={() => openTranslatorForm(translator)} disabled={!canWrite}>编辑</button></td></tr>)}
            </DataTable>
          </section>
        ) : null}

        {!loading && view === "rates" ? (
          <section className="content-panel">
            <div className="section-heading"><div><p className="eyebrow">计价基线</p><h2>费率表</h2></div><span className="section-note">{role === "agent" ? "Agent 的更改将进入审核" : "最新费率覆盖同译员与语言对"}</span></div>
            {(canWrite || canSubmit) ? <form className="form-panel compact" onSubmit={(event) => void saveRate(event)}>
              <div className="form-grid">
                <Field label="译员"><select required value={rateForm.translatorId} onChange={(event) => setRateForm({ ...rateForm, translatorId: event.target.value })}>{workspace.translators.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
                <Field label="语言对"><input required value={rateForm.languagePair} onChange={(event) => setRateForm({ ...rateForm, languagePair: event.target.value })} /></Field>
                <Field label="每字费率"><input required type="number" min="0" step="0.0001" value={rateForm.rate} onChange={(event) => setRateForm({ ...rateForm, rate: event.target.value })} /></Field>
                <Field label="币种"><select value={rateForm.currency} onChange={(event) => setRateForm({ ...rateForm, currency: event.target.value })}><option>CNY</option><option>USD</option><option>EUR</option></select></Field>
              </div>
              <button className="primary-button" disabled={busy || !rateForm.translatorId}>{role === "agent" ? "提交费率提案" : "保存费率"}</button>
            </form> : <ReadOnlyNotice />}
            <DataTable columns={["译员", "语言对", "费率 / 字", "币种", "更新时间"]} empty={workspace.rates.length === 0}>
              {workspace.rates.map((rate: Rate) => <tr key={rate.id}><td><strong>{translatorName(workspace.translators, rate.translatorId)}</strong></td><td><span className="pair-pill">{rate.languagePair}</span></td><td className="number-cell">{formatRate(rate.rateMicros)}</td><td>{rate.currency}</td><td>{rate.updatedAt.slice(0, 10)}</td></tr>)}
            </DataTable>
          </section>
        ) : null}

        {!loading && view === "pos" ? (
          <section className="content-panel">
            <div className="section-heading"><div><p className="eyebrow">交付结算</p><h2>Purchase Orders</h2></div><span className="section-note">金额由字数 × 单价在服务端计算</span></div>
            {(canWrite || canSubmit) ? <form className="form-panel compact" onSubmit={(event) => void savePo(event)}>
              <div className="form-grid wide">
                <Field label="PO 号"><input required value={poForm.poNumber} onChange={(event) => setPoForm({ ...poForm, poNumber: event.target.value })} placeholder="PO-DEMO-260703" /></Field>
                <Field label="译员"><select required value={poForm.translatorId} onChange={(event) => setPoForm({ ...poForm, translatorId: event.target.value })}>{workspace.translators.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
                <Field label="月份"><input required type="month" value={poForm.month} onChange={(event) => setPoForm({ ...poForm, month: event.target.value })} /></Field>
                <Field label="语言对"><input required value={poForm.languagePair} onChange={(event) => setPoForm({ ...poForm, languagePair: event.target.value })} /></Field>
                <Field label="字数"><input required type="number" min="0" step="1" value={poForm.wordCount} onChange={(event) => setPoForm({ ...poForm, wordCount: event.target.value })} /></Field>
                <Field label="单价 / 字"><input required type="number" min="0" step="0.0001" value={poForm.unitRate} onChange={(event) => setPoForm({ ...poForm, unitRate: event.target.value })} /></Field>
                <Field label="币种"><select value={poForm.currency} onChange={(event) => setPoForm({ ...poForm, currency: event.target.value })}><option>CNY</option><option>USD</option><option>EUR</option></select></Field>
                <Field label="初始状态"><select value={poForm.status} onChange={(event) => setPoForm({ ...poForm, status: event.target.value as PoStatus })}><option value="draft">草稿</option><option value="confirmed">已确认</option></select></Field>
              </div>
              <div className="form-footer"><span>预计金额：<strong>{formatCurrency(calculateAmountCents(Number(poForm.wordCount || 0), parseRateMicros(poForm.unitRate || 0)), poForm.currency)}</strong></span><button className="primary-button" disabled={busy || !poForm.translatorId}>{role === "agent" ? "提交 PO 提案" : "新增 PO"}</button></div>
            </form> : <ReadOnlyNotice />}
            <DataTable columns={["PO 号", "译员 / 语言对", "月份", "字数", "金额", "状态"]} empty={workspace.purchaseOrders.length === 0}>
              {workspace.purchaseOrders.map((po: PurchaseOrder) => <tr key={po.id}><td><strong>{po.poNumber}</strong></td><td>{translatorName(workspace.translators, po.translatorId)}<small>{po.languagePair}</small></td><td>{po.month}</td><td className="number-cell">{po.wordCount.toLocaleString("zh-CN")}</td><td className="number-cell">{formatCurrency(po.amountCents, po.currency)}</td><td>{canWrite ? <select className="status-select" value={po.status} aria-label={`${po.poNumber} 状态`} onChange={(event) => void mutate(`/api/pos/${po.id}`, "PATCH", { status: event.target.value }, "PO 状态已更新")} disabled={busy}><option value="draft">草稿</option><option value="confirmed">已确认</option><option value="paid">已付</option></select> : <StatusTag status={po.status} />}</td></tr>)}
            </DataTable>
          </section>
        ) : null}

        {!loading && view === "approvals" ? (
          <section className="content-panel">
            <div className="section-heading"><div><p className="eyebrow">权限闸口</p><h2>审核流</h2></div><span className="section-note">Agent 提案 → Boss 批准后原子写入</span></div>
            {!canReview ? <ReadOnlyNotice text={role === "agent" ? "Agent 可在费率或 PO 页提交提案，但不能批准自己的提案。" : "仅 Boss 可批准或驳回待审项。"} /> : null}
            <div className="approval-list">
              {workspace.approvals.length ? workspace.approvals.map((approval) => (
                <article className="approval-card" key={approval.id}>
                  <div className="approval-main"><span className="kind-tag">{approval.kind === "rate" ? "费率提案" : "PO 提案"}</span><h3>{formatApprovalSummary(approval, workspace.translators)}</h3><p>{approval.submittedBy} · {approval.createdAt.slice(0, 16).replace("T", " ")}</p>{approval.note ? <p className="review-note">审核意见：{approval.note}</p> : null}</div>
                  <div className="approval-actions"><StatusTag status={approval.status} />{approval.status === "pending" && canReview ? <><button className="approve-button" disabled={busy} onClick={() => void mutate(`/api/approvals/${approval.id}`, "PATCH", { status: "approved", note: "核对无误，批准写入" }, "审核已批准，业务数据已写入")}>批准并写入</button><button className="reject-button" disabled={busy} onClick={() => void mutate(`/api/approvals/${approval.id}`, "PATCH", { status: "rejected", note: "信息不完整，请更正后重提" }, "审核已驳回")}>驳回</button></> : null}</div>
                </article>
              )) : <EmptyState text="尚无审核记录。Agent 提交费率或 PO 提案后将显示在这里。" />}
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}

function Metric({ label, value, note, compact = false }: { label: string; value: string; note: string; compact?: boolean }) {
  return <article className="metric"><span>{label}</span><strong className={compact ? "compact" : undefined}>{value}</strong><small>{note}</small></article>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

function DataTable({ columns, empty, children }: { columns: string[]; empty: boolean; children: React.ReactNode }) {
  if (empty) return <EmptyState text="当前没有匹配记录，可调整条件或新增数据。" />;
  return <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;
}

function StatusTag({ status }: { status: string }) {
  const labels: Record<string, string> = { active: "在库", inactive: "停用", draft: "草稿", confirmed: "已确认", paid: "已付", pending: "待审", approved: "已批准", rejected: "已驳回" };
  return <span className={`status-tag ${status}`}>{labels[status] ?? status}</span>;
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state"><span aria-hidden="true">{"· · ·"}</span><p>{text}</p></div>;
}

function ReadOnlyNotice({ text = "当前 Demo 角色只能查看此页数据。" }: { text?: string }) {
  return <div className="read-only-notice" role="note">{text}</div>;
}
