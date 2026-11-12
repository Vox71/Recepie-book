import { Link } from 'react-router'
import Icon from '../components/Icon'
import { PlaceholderLine } from '../components/Placeholders'

export default function RecipePage() {
  return <main className="container recipe-page">
    <nav className="breadcrumbs" aria-label="Хлебные крошки"><Link to="/">← Лента рецептов</Link><span aria-hidden="true">/</span><span>Рецепт</span></nav>
    <p className="data-note">Данные рецепта пока не подключены. Ниже — шаблон страницы без выдуманных ингредиентов и инструкций.</p>
    <section className="recipe-hero" aria-labelledby="recipe-title">
      <div className="recipe-hero-photo image-placeholder"><Icon name="image" size={48}/><span>Здесь появится фотография блюда</span></div>
      <div className="recipe-summary"><p className="eyebrow">Простое удовольствие</p><h1 id="recipe-title">Название рецепта</h1><p className="intro">Здесь появится описание блюда и его особенности.</p><div className="recipe-facts" aria-label="Характеристики пока не указаны"><span><Icon name="clock"/>Время —</span><span><Icon name="chef"/>Сложность —</span><span><Icon name="users"/>Порции —</span></div><div className="ingredient-notice"><Icon name="fridge" size={24}/><div><strong>Ингредиенты из вашего холодильника</strong><p>Совпадения появятся после подключения данных.</p></div></div><button className="secondary-button" disabled><Icon name="heart"/>В избранное</button></div>
    </section>
    <div className="recipe-details">
      <section className="ingredients-panel" aria-labelledby="ingredients-title"><div className="section-heading"><h2 id="ingredients-title">Ингредиенты</h2><span className="section-caption">Порции —</span></div><p className="small-note">Состав и количество пока не указаны.</p><div className="ingredient-rows" aria-hidden="true">{Array.from({ length: 7 }, (_, i) => <div className="ingredient-row" key={i}><Icon name="check" size={18}/><div><PlaceholderLine width="78%"/><PlaceholderLine width="58%"/></div><PlaceholderLine width="48px"/></div>)}</div><div className="allergen-note"><Icon name="wheat" size={18}/>Сведения об аллергенах пока отсутствуют.</div></section>
      <section className="steps-panel" aria-labelledby="steps-title"><div className="section-heading"><h2 id="steps-title">Готовим шаг за шагом</h2></div><p className="small-note">Здесь появятся инструкции по приготовлению.</p><div className="step-placeholders" aria-hidden="true">{Array.from({ length: 4 }, (_, i) => <div className="step-placeholder" key={i}><span className="step-marker"><Icon name="chef" size={20}/></span><div><PlaceholderLine width="46%"/><PlaceholderLine/><PlaceholderLine width="86%"/></div></div>)}</div><div className="recipe-source"><Icon name="info" size={16}/><span>Ссылка на источник появится вместе с рецептом.</span></div></section>
    </div>
  </main>
}
