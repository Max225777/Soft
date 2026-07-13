export default function LegalFooter() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 16, padding: '20px 0 8px' }}>
      <a href="/terms" target="_blank" style={{ fontSize: 11, color: 'var(--muted)', textDecoration: 'none' }}>Соглашение</a>
      <a href="/privacy" target="_blank" style={{ fontSize: 11, color: 'var(--muted)', textDecoration: 'none' }}>Конфиденциальность</a>
      <a href="/info" target="_blank" style={{ fontSize: 11, color: 'var(--muted)', textDecoration: 'none' }}>Информация</a>
    </div>
  )
}
