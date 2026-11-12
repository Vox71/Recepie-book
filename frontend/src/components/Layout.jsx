import { Link, NavLink, Outlet, useLocation } from 'react-router'
import Brand from './Brand'
import Icon from './Icon'

export default function Layout() {
  const isRecipe = useLocation().pathname.startsWith('/recipes/')
  return <div className="app">
    <header className="site-header"><div className="container header-inner">
      <Brand />
      <nav className="main-nav" aria-label="Основная навигация">
        <NavLink className={({ isActive }) => `nav-item${isActive || isRecipe ? ' active' : ''}`} to="/" end>Лента</NavLink>
        <NavLink className="nav-item" to="/fridge">Мой холодильник</NavLink>
        <NavLink className="nav-item" to="/favorites">Избранное</NavLink>
      </nav>
      <Link className="login-link" to="/login">Войти <Icon name="arrow" size={16}/></Link>
    </div></header>
    <Outlet />
    <footer className="site-footer"><div className="container footer-inner">
      <span className="footer-brand">Recepie Book</span>
      <span>Меньше лишних покупок. Больше вкусных идей.</span>
      <span>© {new Date().getFullYear()}</span>
    </div></footer>
  </div>
}
