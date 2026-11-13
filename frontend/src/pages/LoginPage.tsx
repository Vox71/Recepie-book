/**
 * Login screen: the markup and nothing else.
 *
 * The form does not call the API yet - `POST /login` and storing the token belong to the
 * next frontend task (docs/sprint-4-plan.md). The fields are here because the address
 * `/login` has to render something real and testable, and because the auth screen is
 * exactly what the timer and recipe pages will need first.
 */
export default function LoginPage() {
  return (
    <section>
      <h2>Вход</h2>
      <form aria-label="Вход в Recepie-book" onSubmit={(event) => event.preventDefault()}>
        <p>
          <label htmlFor="email">Электронная почта</label>
          <input id="email" name="email" type="email" autoComplete="email" required />
        </p>
        <p>
          <label htmlFor="password">Пароль</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        </p>
        <button type="submit">Войти</button>
      </form>
      <p>Отправка формы и авторизация появятся в следующей задаче фронтенда.</p>
    </section>
  );
}
