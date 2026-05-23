// Global app context — exposes { state, dispatch, toast, confirm, nav } to
// any descendant via useApp(). Toast queue + Confirm dialog live in state so
// they survive across views.

const AppContext = React.createContext(null);
const useApp = () => React.useContext(AppContext);

/* ── Toast viewport ─────────────────────────────────────────────── */
const ToastViewport = () => {
  const { state, dispatch } = useApp();
  const toasts = state.toasts || [];
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex flex-col gap-2 items-end">
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} onClose={() => dispatch({ type: "dismissToast", id: t.id })} />
      ))}
    </div>
  );
};

const ToastItem = ({ toast, onClose }) => {
  React.useEffect(() => {
    const ms = toast.duration ?? 2600;
    const h = setTimeout(onClose, ms);
    return () => clearTimeout(h);
  }, []);
  const kind = toast.kind || "default";
  const icon = kind === "success" ? "check" : kind === "danger" ? "info" : kind === "info" ? "info" : "sparkle";
  const accent = kind === "success" ? "text-emerald-600 dark:text-emerald-400"
              : kind === "danger" ? "text-rose-600 dark:text-rose-400"
              : kind === "info" ? "text-sky-600 dark:text-sky-400"
              : "text-brand";
  return (
    <div className="pointer-events-auto flex items-center gap-2.5 rounded-lg border bg-popover/95 backdrop-blur-md px-3.5 py-2.5 shadow-lg min-w-[200px] max-w-[360px] animate-slide-in">
      <span className={cn("grid h-5 w-5 place-items-center rounded-full bg-muted/40", accent)}>
        <Icon name={icon} className="h-3 w-3" />
      </span>
      <div className="flex-1 min-w-0">
        {toast.title && <div className="text-[12.5px] font-semibold leading-tight">{toast.title}</div>}
        <div className={cn("text-[12.5px] leading-snug", toast.title && "text-muted-foreground mt-0.5")}>{toast.message}</div>
      </div>
      {toast.action && (
        <button onClick={() => { toast.action.onClick?.(); onClose(); }}
          className="font-mono text-[11px] text-brand hover:underline whitespace-nowrap">
          {toast.action.label}
        </button>
      )}
      <button onClick={onClose}
        className="text-muted-foreground hover:text-foreground transition-colors">
        <Icon name="x" className="h-3 w-3" />
      </button>
    </div>
  );
};

/* ── Confirm dialog ─────────────────────────────────────────────── */
const ConfirmDialog = () => {
  const { state, dispatch } = useApp();
  const c = state.confirm;
  const close = () => dispatch({ type: "closeConfirm" });
  if (!c) return null;
  const onOk = () => { c.onConfirm?.(); close(); };
  return (
    <Dialog open={true} onOpenChange={close}>
      <DialogContent className="w-[420px]">
        <header className="flex items-start gap-3 px-5 pt-5 pb-3">
          <div className={cn("grid h-9 w-9 place-items-center rounded-full flex-shrink-0",
            c.danger ? "bg-destructive/10 text-destructive" : "bg-brand/10 text-brand"
          )}>
            <Icon name={c.danger ? "trash" : "info"} className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-[15px] font-semibold tracking-tight">{c.title || "确认操作"}</h3>
            {c.desc && (
              <p className="text-[12.5px] text-muted-foreground mt-1 leading-relaxed" style={{ textWrap: "pretty" }}>
                {c.desc}
              </p>
            )}
          </div>
        </header>
        <footer className="flex items-center justify-end gap-2 border-t bg-muted/20 px-5 py-3">
          <Button variant="outline" size="sm" onClick={close}>{c.cancelLabel || "取消"}</Button>
          <Button variant={c.danger ? "destructive" : "brand"} size="sm" onClick={onOk}>
            {c.confirmLabel || (c.danger ? "删除" : "确认")}
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  );
};

/* ── Provider that wraps state + dispatch + helpers ─────────────── */
const AppProvider = ({ state, dispatch, children }) => {
  // Helper API. Stable across renders.
  const toast = React.useCallback((msg, opts = {}) => {
    const message = typeof msg === "string" ? msg : msg.message;
    const rest = typeof msg === "string" ? opts : { ...msg, ...opts };
    dispatch({
      type: "pushToast",
      toast: { id: "t" + Date.now() + Math.random().toString(36).slice(2, 6), message, ...rest },
    });
  }, [dispatch]);

  const confirm = React.useCallback((payload) => {
    dispatch({ type: "openConfirm", payload });
  }, [dispatch]);

  const nav = React.useCallback((patch) => {
    dispatch({ type: "set", patch: { ...patch } });
  }, [dispatch]);

  const value = React.useMemo(
    () => ({ state, dispatch, toast, confirm, nav }),
    [state, dispatch, toast, confirm, nav]
  );

  return (
    <AppContext.Provider value={value}>
      {children}
      <ToastViewport />
      <ConfirmDialog />
    </AppContext.Provider>
  );
};

Object.assign(window, { AppContext, AppProvider, useApp, ToastViewport, ConfirmDialog });
