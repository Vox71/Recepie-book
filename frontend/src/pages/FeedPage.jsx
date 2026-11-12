import Icon from '../components/Icon'
import { RecipeCardPlaceholder, SearchField } from '../components/Placeholders'

export default function FeedPage() {
  return <main className="container feed">
    <p className="eyebrow">Вдохновение на каждый день</p>
    <h1>Что приготовим сегодня?</h1>
    <p className="intro">Начните с того, что уже есть дома. А мы подскажем вкусные сочетания.</p>
    <SearchField placeholder="Поиск по названию или ингредиентам — например, томаты" label="Поиск рецептов" hintId="feed-hint"/>
    <div className="filters" aria-label="Фильтры рецептов">
      <label className="difficulty-filter"><span>Сложность</span><select disabled aria-describedby="feed-hint"><option>Любая</option></select></label>
      <span className="filter-divider"/><span className="filter-label">Предпочтения</span>
      <button className="chip selected" disabled>Все рецепты</button><button className="chip" disabled>Без мяса</button><button className="chip" disabled>Без глютена</button>
    </div>
    <section className="feature-banner feed-banner" aria-labelledby="banner-heading">
      <div className="banner-copy"><h2 id="banner-heading"><Icon name="sprout" size={24}/>Вдохновение из вашего холодильника</h2><p>Знакомые продукты — новые сочетания. Здесь появятся идеи блюд из того, что есть дома.</p></div>
      <img src="/images/tomatoes-banner.png" alt=""/>
    </section>
    <section aria-labelledby="recipes-heading">
      <div className="section-heading"><div><h2 id="recipes-heading">Из вашего холодильника</h2><p>Знакомые продукты — новые поводы собраться за столом.</p></div></div>
      <p className="data-note" id="feed-hint">Рецепты пока не загружены. Ниже показаны места для будущих карточек; поиск и фильтры пока недоступны.</p>
      <div className="recipe-grid">{Array.from({ length: 6 }, (_, i) => <RecipeCardPlaceholder key={i}/>)}</div>
      <p className="footnote"><Icon name="info" size={17}/>Учитываем только продукты с актуальным сроком годности. Масло, соль и другие добавки проверяйте отдельно.</p>
    </section>
  </main>
}
