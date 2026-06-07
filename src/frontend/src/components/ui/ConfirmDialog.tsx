import { Button, Dialog, DialogContent, Icon } from './index'

export interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = '确认',
  cancelLabel = '取消',
  danger = false,
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent className="w-[400px]">
        <header className="flex items-center gap-2 border-b px-4 py-3">
          <Icon
            name={danger ? 'shieldCheck' : 'info'}
            className={danger ? 'h-4 w-4 text-red-500' : 'h-4 w-4 text-brand'}
          />
          <h3 className="flex-1 text-[15px] font-medium">{title}</h3>
          <Button variant="ghost" size="iconSm" onClick={onCancel}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        <div className="px-4 py-4">
          <p className="text-[13px] leading-relaxed text-muted-foreground">{message}</p>
        </div>

        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={danger ? 'destructive' : 'brand'}
            size="sm"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? '处理中…' : confirmLabel}
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}
