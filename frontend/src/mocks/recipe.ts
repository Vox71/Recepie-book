/**
 * Mock data of the recipe screen (sprint 3, task 4: layout only).
 *
 * The page has no API call yet: `GET /recipes/{id}` and the real steps/nutrition come in
 * sprint 4 (`docs/sprint-4-plan.md`). The shapes below are deliberately close to the
 * `Recipe`, `RecipeStep` and `RecipeNutrition` schemas of `openapi.yaml`, so switching to
 * the API changes the loader, not the markup.
 *
 * The texts repeat the mockup `frontend/design/02 — Страница рецепта.png`.
 */
export interface RecipeIngredient {
  name: string;
  quantity: string;
  /** In the mockup this is the green check ("Есть в холодильнике") vs the plus. */
  available: boolean;
}

export interface RecipeStep {
  title: string;
  description: string;
  minutes: number;
}

export interface RecipeView {
  id: number;
  title: string;
  eyebrow: string;
  description: string;
  minutes: number;
  difficulty: string;
  servings: number;
  badge: string;
  /** Display text of the missing ingredients ("масло и соль"), as in the mockup. */
  missing: string;
  allergens: string[];
  ingredients: RecipeIngredient[];
  steps: RecipeStep[];
  source: { title: string; url: string; note: string };
}

export const recipeMock: RecipeView = {
  id: 1,
  title: 'Овощная паста с томатами',
  eyebrow: 'Простое удовольствие',
  description:
    'Сочные томаты, нежный кабачок и немного зелени. Лёгкий домашний ужин из знакомых продуктов.',
  minutes: 25,
  difficulty: 'Легко',
  servings: 2,
  badge: 'Томаты пригодятся сегодня',
  missing: 'масло и соль',
  allergens: ['глютен'],
  ingredients: [
    { name: 'Паста', quantity: '200 г', available: true },
    { name: 'Томаты', quantity: '4 шт.', available: true },
    { name: 'Кабачок', quantity: '1 шт.', available: true },
    { name: 'Шпинат', quantity: '80 г', available: true },
    { name: 'Чеснок', quantity: '2 зубчика', available: true },
    { name: 'Оливковое масло', quantity: '2 ст. л.', available: false },
    { name: 'Соль', quantity: 'по вкусу', available: false },
  ],
  steps: [
    {
      title: 'Подготовьте овощи',
      minutes: 5,
      description:
        'Вымойте томаты, кабачок и шпинат. Томаты нарежьте крупными кусочками, кабачок — полукружьями. Очистите и мелко порубите чеснок.',
    },
    {
      title: 'Отварите пасту',
      minutes: 10,
      description:
        'Доведите подсоленную воду до кипения. Варите 200 г пасты до состояния аль денте по инструкции на упаковке. Сохраните немного воды от варки.',
    },
    {
      title: 'Приготовьте овощи',
      minutes: 7,
      description:
        'Разогрейте оливковое масло в сковороде. Добавьте кабачок и обжаривайте 4 минуты. Положите чеснок и томаты, готовьте ещё 3 минуты, помешивая.',
    },
    {
      title: 'Соедините и подавайте',
      minutes: 3,
      description:
        'Добавьте шпинат, готовую пасту и немного воды от варки. Перемешайте и прогрейте 2–3 минуты, пока шпинат не станет мягким. Посолите по вкусу и подавайте.',
    },
  ],
  source: {
    title: 'BBC Good Food',
    url: 'https://www.bbcgoodfood.com/',
    note: 'Домашняя адаптация по мотивам подборки вегетарианской пасты.',
  },
};
