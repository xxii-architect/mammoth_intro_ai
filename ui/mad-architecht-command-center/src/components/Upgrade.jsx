export default function Upgrade({
  title = "Upgrade NotesPanel to Command Center style with layered dark cards and high-contrast readable text",
  eyebrow = "Atlas UI",
  children,
  tone = "cyan",
  className = "",
  footer,
}) {
  const classes = ["atlas-card", `tone-${tone}`, className].filter(Boolean).join(" ")

  return (
    <article className={classes} data-tone={tone}>
      <header className="atlas-card__header">
        <p className="atlas-card__eyebrow">{eyebrow}</p>
        <h3 className="atlas-card__title">{title}</h3>
      </header>
      <div className="atlas-card__body">
        {children ?? <p className="atlas-card__copy">Upgrade NotesPanel to Command Center style with layered dark cards and high-contrast readable text</p>}
      </div>
      {footer ? <footer className="atlas-card__footer">{footer}</footer> : null}
    </article>
  )
}
