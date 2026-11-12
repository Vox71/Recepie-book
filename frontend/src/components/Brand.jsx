import { Link } from 'react-router'
import Icon from './Icon'

export default function Brand() {
  return <Link className="brand" to="/" aria-label="Recepie Book — главная"><span className="brand-icon"><Icon name="sprout" size={23}/></span><span>Recepie Book</span></Link>
}
