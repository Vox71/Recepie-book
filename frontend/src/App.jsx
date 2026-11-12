import { BrowserRouter, Link, Route, Routes } from 'react-router'
import Layout from './components/Layout'
import FeedPage from './pages/FeedPage'
import FridgePage from './pages/FridgePage'
import FavoritesPage from './pages/FavoritesPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import RecipePage from './pages/RecipePage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="register" element={<RegisterPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route element={<Layout />}>
          <Route index element={<FeedPage />} />
          <Route path="fridge" element={<FridgePage />} />
          <Route path="recipes/:id" element={<RecipePage />} />
          <Route path="favorites" element={<FavoritesPage />} />
          <Route
            path="*"
            element={
              <main className="container feed">
                <h1>Страница не найдена</h1>
                <Link className="back-link" to="/">
                  Вернуться в ленту →
                </Link>
              </main>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}