import Icon from './Icon'

// Неподвижные заглушки показывают структуру макета, а не процесс загрузки.
export function PlaceholderLine({ width = '100%' }) {
  return <span className="placeholder-line" style={{ width }} aria-hidden="true" />
}

export function RecipeCardPlaceholder() {
  return <div className="recipe-card" aria-hidden="true">
    <div className="recipe-photo image-placeholder"><Icon name="image" size={36}/><span>Фото рецепта</span><span className="favorite-placeholder"><Icon name="heart"/></span></div>
    <div className="recipe-body">
      <div className="recipe-meta"><Icon name="clock" size={16}/><PlaceholderLine width="52px"/><PlaceholderLine width="44px"/></div>
      <div className="recipe-title-placeholder"><PlaceholderLine width="88%"/></div>
      <div className="ingredient-match"><Icon name="fridge" size={16}/><PlaceholderLine width="62%"/></div>
    </div>
  </div>
}

export function ProductCardPlaceholder({ icon = 'leaf' }) {
  return <div className="product-card" aria-hidden="true">
    <div className="product-top"><span className="product-icon"><Icon name={icon} size={24}/></span><PlaceholderLine width="64px"/></div>
    <div className="product-name-placeholder"><PlaceholderLine width="65%"/></div>
    <PlaceholderLine width="76%"/>
    <div className="product-status-placeholder"><span/><PlaceholderLine width="48%"/></div>
  </div>
}

export function SearchField({ placeholder, label, hintId }) {
  return <div className="search-field"><Icon name="search"/><input type="search" aria-label={label} aria-describedby={hintId} placeholder={placeholder} disabled/></div>
}
