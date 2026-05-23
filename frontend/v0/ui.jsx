// shadcn-style primitives — Button, Avatar, Badge, Separator, ScrollArea, Tabs, etc.
// Tailwind-only, single file.

const cn = (...args) => args.filter(Boolean).join(" ");

/* Button — variants: default, secondary, outline, ghost, destructive, link */
const Button = React.forwardRef(({ variant = "default", size = "default", className = "", children, ...props }, ref) => {
  const base = "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 gap-2";
  const variants = {
    default:     "bg-primary text-primary-foreground hover:bg-primary/90",
    brand:       "bg-brand text-brand-foreground hover:bg-brand/90 shadow-sm",
    secondary:   "bg-secondary text-secondary-foreground hover:bg-secondary/80",
    outline:     "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
    ghost:       "hover:bg-accent hover:text-accent-foreground",
    destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
    link:        "text-primary underline-offset-4 hover:underline",
  };
  const sizes = {
    default: "h-9 px-4 py-2",
    sm:      "h-8 rounded-md px-3 text-xs",
    lg:      "h-10 rounded-md px-6",
    icon:    "h-9 w-9",
    iconSm:  "h-8 w-8",
  };
  return (
    <button ref={ref} className={cn(base, variants[variant], sizes[size], className)} {...props}>
      {children}
    </button>
  );
});

/* Avatar — solid + initial */
const Avatar = ({ initial, color = "neutral", size = 24, online, className = "" }) => {
  const palettes = {
    brand:   "bg-brand text-brand-foreground",
    neutral: "bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200",
    sage:    "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
    clay:    "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    rose:    "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300",
    blue:    "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  };
  return (
    <div className={cn("relative inline-flex items-center justify-center rounded-full font-medium flex-shrink-0", palettes[color] || palettes.neutral, className)}
         style={{ width: size, height: size, fontSize: Math.max(10, size * 0.42) }}>
      <span className="leading-none">{initial}</span>
      {online !== undefined && (
        <span className={cn("absolute -bottom-0.5 -right-0.5 rounded-full border-2 border-background",
                            online ? "bg-emerald-500" : "bg-zinc-400")}
              style={{ width: Math.max(7, size * 0.28), height: Math.max(7, size * 0.28) }}/>
      )}
    </div>
  );
};

/* Badge — variants */
const Badge = ({ variant = "default", className = "", children }) => {
  const variants = {
    default:    "border-transparent bg-primary text-primary-foreground",
    secondary:  "border-transparent bg-secondary text-secondary-foreground",
    outline:    "text-foreground",
    brand:      "border-transparent bg-brand/10 text-brand dark:bg-brand/20",
    success:    "border-transparent bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
    warning:    "border-transparent bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    destructive:"border-transparent bg-destructive/10 text-destructive",
  };
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10.5px] font-mono uppercase tracking-wider", variants[variant], className)}>
      {children}
    </span>
  );
};

/* Separator */
const Separator = ({ orientation = "horizontal", className = "" }) => (
  <div className={cn("shrink-0 bg-border",
    orientation === "horizontal" ? "h-px w-full" : "w-px h-full",
    className)}/>
);

/* Tooltip-y kbd */
const Kbd = ({ children }) => (
  <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
    {children}
  </kbd>
);

/* Card */
const Card = ({ className = "", children, ...props }) => (
  <div className={cn("rounded-xl border bg-card text-card-foreground", className)} {...props}>{children}</div>
);
const CardHeader = ({ className = "", children }) => (
  <div className={cn("flex flex-col space-y-1.5 p-4", className)}>{children}</div>
);
const CardTitle = ({ className = "", children }) => (
  <h3 className={cn("text-base font-semibold leading-none tracking-tight", className)}>{children}</h3>
);
const CardDescription = ({ className = "", children }) => (
  <p className={cn("text-sm text-muted-foreground", className)}>{children}</p>
);
const CardContent = ({ className = "", children }) => (
  <div className={cn("p-4 pt-0", className)}>{children}</div>
);

/* Input */
const Input = React.forwardRef(({ className = "", ...props }, ref) => (
  <input ref={ref}
    className={cn("flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50", className)}
    {...props}/>
));

/* Textarea */
const Textarea = React.forwardRef(({ className = "", ...props }, ref) => (
  <textarea ref={ref}
    className={cn("flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50", className)}
    {...props}/>
));

/* Tabs */
const Tabs = ({ value, onValueChange, children, className = "" }) => {
  const ctx = { value, onValueChange };
  return <TabsCtx.Provider value={ctx}><div className={className}>{children}</div></TabsCtx.Provider>;
};
const TabsCtx = React.createContext({});
const TabsList = ({ className = "", children }) => (
  <div className={cn("inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground", className)}>
    {children}
  </div>
);
const TabsTrigger = ({ value, className = "", children }) => {
  const ctx = React.useContext(TabsCtx);
  const on = ctx.value === value;
  return (
    <button onClick={() => ctx.onValueChange(value)}
      data-state={on ? "active" : "inactive"}
      className={cn("inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        on ? "bg-background text-foreground shadow" : "hover:text-foreground",
        className)}>
      {children}
    </button>
  );
};

/* Dialog */
const Dialog = ({ open, onOpenChange, children }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm"
           onClick={() => onOpenChange(false)}/>
      <div className="relative z-10 animate-slide-in">{children}</div>
    </div>
  );
};
const DialogContent = ({ className = "", children }) => (
  <div className={cn("w-[560px] max-w-[calc(100vw-2rem)] max-h-[85vh] flex flex-col rounded-xl border bg-background shadow-lg", className)}>
    {children}
  </div>
);

window.cn = cn;
window.Button = Button;
window.Avatar = Avatar;
window.Badge = Badge;
window.Separator = Separator;
window.Kbd = Kbd;
window.Card = Card;
window.CardHeader = CardHeader;
window.CardTitle = CardTitle;
window.CardDescription = CardDescription;
window.CardContent = CardContent;
window.Input = Input;
window.Textarea = Textarea;
window.Tabs = Tabs;
window.TabsList = TabsList;
window.TabsTrigger = TabsTrigger;
window.Dialog = Dialog;
window.DialogContent = DialogContent;
