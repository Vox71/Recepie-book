import { Link } from 'react-router'
import Brand from './Brand'
import Icon from './Icon'

export default function AuthLayout({ registration = false, children }) {
  return <div className={`app auth-page${registration ? ' registration-page' : ''}`}>
    <header className="container login-header"><Brand/><div className="auth-switch"><span>{registration ? 'Уже есть аккаунт?' : 'Впервые здесь?'}</span><Link to={registration ? '/login' : '/register'}>{registration ? 'Войти' : 'Создать аккаунт'} <Icon name="arrow" size={16}/></Link></div></header>
    <main className="login-main"><section className="login-story" aria-labelledby="story-title"><img className="auth-photo" src="/images/pasta-tomatoes.png" alt=""/><div className="login-story-copy"><p className="eyebrow"><Icon name="sprout" size={18}/>{registration ? 'Вкусные привычки начинаются дома' : 'Просто. Вкусно. По-домашнему.'}</p><h2 id="story-title">{registration ? <>Ваша кухня.<br/>Ваши любимые рецепты.</> : <>Готовьте из того,<br/>что уже есть</>}</h2><p>{registration ? 'Собирайте любимые блюда, следите за продуктами и находите вдохновение для каждого дня.' : 'Любимые продукты, новые сочетания и маленькая радость от домашнего ужина.'}</p></div></section><section className="login-panel" aria-labelledby={registration ? 'register-title' : 'login-title'}><div className="login-form-container">{children}</div></section></main>
    <footer className="container login-footer"><span>© {new Date().getFullYear()} Recepie Book</span><span>Хорошая еда начинается дома</span></footer>
  </div>
}
