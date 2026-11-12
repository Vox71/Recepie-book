import EmptyState from '../components/EmptyState'

export default function FavoritesPage() {
  return (
    <main className="container feed">
      <p className="eyebrow">Ваша коллекция</p>
      <h1>Избранное</h1>
      <p className="intro">
        Любимые рецепты, к которым хочется возвращаться.
      </p>

      <EmptyState title="Избранных рецептов пока нет">
        Здесь появятся сохранённые рецепты.
      </EmptyState>
    </main>
  )
}