import { Link } from 'react-router'
import Icon from '../components/Icon'
import { ProductCardPlaceholder, SearchField } from '../components/Placeholders'

export default function FridgePage() {
  return <main className="container feed fridge-page">
    <p className="eyebrow">Ваша кухня</p>
    <div className="page-title-row"><div><h1>Мой холодильник</h1><p className="intro">Всё, что есть дома, — начало чего-то вкусного.</p></div><button className="primary-button" disabled aria-describedby="fridge-hint"><Icon name="plus"/>Добавить продукт</button></div>
    <section className="feature-banner fridge-banner" aria-labelledby="fridge-banner-title"><div className="banner-copy"><p className="banner-eyebrow"><Icon name="clock" size={18}/>Вдохновение для вашей кухни</p><h2 id="fridge-banner-title">Пусть ничего не пропадёт</h2><p>Здесь появятся подсказки о сроках годности и идеи блюд из ваших продуктов.</p><Link className="primary-button" to="/"><Icon name="arrow"/>В ленту рецептов</Link></div><img src="/images/tomatoes-banner.png" alt=""/></section>
    <section aria-labelledby="products-heading">
      <div className="section-heading"><h2 id="products-heading">Ваши продукты</h2><span className="section-caption">Сначала — с ближайшим сроком годности</span></div>
      <div className="fridge-filters"><SearchField placeholder="Найти продукт в холодильнике" label="Поиск продуктов" hintId="fridge-hint"/><div className="filter-chips"><button className="chip selected" disabled>Все</button><button className="chip" disabled>Скоро испортятся</button><button className="chip" disabled>Просрочены</button></div></div>
      <p className="data-note" id="fridge-hint">В холодильнике пока нет продуктов. Карточки показывают структуру страницы; добавление и поиск пока недоступны.</p>
      <div className="product-grid">{['sprout', 'leaf', 'leaf', 'wheat', 'sprout', 'egg', 'bottle'].map((icon, i) => <ProductCardPlaceholder icon={icon} key={i}/>)}<aside className="dinner-card"><Icon name="chef" size={26}/><h3>Что на ужин?</h3><p>Найдите вдохновение в том, что у вас под рукой.</p><Link to="/">В ленту рецептов <Icon name="arrow" size={16}/></Link></aside></div>
      <p className="footnote"><Icon name="info" size={17}/>Перед приготовлением проверяйте свежесть продуктов.</p>
    </section>
  </main>
}
