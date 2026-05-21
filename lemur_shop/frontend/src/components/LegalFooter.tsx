export default function LegalFooter() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', gap: 16, padding: '20px 0 8px' }}>
      <a href="/offer.html" target="_blank" style={{ fontSize: 11, color: 'var(--muted)', textDecoration: 'none' }}>Оферта</a>
      <a href="/privacy.html" target="_blank" style={{ fontSize: 11, color: 'var(--muted)', textDecoration: 'none' }}>Конфиденциальность</a>
      <a href="/returns.html" target="_blank" style={{ fontSize: 11, color: 'var(--muted)', textDecoration: 'none' }}>Возврат</a>
    </div>
  )
}
