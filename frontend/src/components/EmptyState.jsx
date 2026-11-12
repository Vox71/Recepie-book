import Icon from './Icon'
export default function EmptyState({ title, children }) {
  return <div className="empty-state"><span className="empty-state-icon"><Icon name="sprout" size={24}/></span><h3>{title}</h3><p>{children}</p></div>
}
