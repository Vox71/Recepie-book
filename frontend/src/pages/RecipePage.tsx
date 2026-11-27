import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import { listFridgeItems } from '../api/fridge';
import { getRecipe } from '../api/recipes';
import type { RecipeDto } from '../api/recipes';
import { useAuth } from '../auth/AuthContext';
import Breadcrumbs from '../components/recipe/Breadcrumbs';
import IngredientsCard from '../components/recipe/IngredientsCard';
import NutritionCard from '../components/recipe/NutritionCard';
import PortionControl from '../components/recipe/PortionControl';
import RecipeHero from '../components/recipe/RecipeHero';
import StepsList from '../components/recipe/StepsList';
import { scaleNutrition, scaleQuantity } from '../components/recipe/portions';
import type { RecipeView } from '../components/recipe/types';
import styles from './RecipePage.module.css';

function parsePositiveInt(value: string): number | null {
  const trimmed = value.trim();
  if (!/^\d+$/.test(trimmed)) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

function normalizeName(value: string): string {
  return value
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[^a-zа-я0-9]+/gi, ' ')
    .trim();
}

function isInFridge(name: string, products: string[]): boolean {
  const target = normalizeName(name);
  if (!target) {
    return false;
  }
  return products.some((product) => {
    const candidate = normalizeName(product);
    return candidate === target || candidate.includes(target) || target.includes(candidate);
  });
}

function sourceLabel(url: string | null): string {
  if (!url) {
    return '';
  }
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return 'Открыть источник';
  }
}

function buildView(
  recipe: RecipeDto,
  servings: number | null,
  factor: number,
  fridgeProducts: string[] | null,
): RecipeView {
  return {
    id: recipe.id,
    title: recipe.name,
    minutes: recipe.cooking_time_minutes,
    difficulty: recipe.difficulty_level,
    servings,
    ingredients: recipe.ingredient_list.map((item) => ({
      name: item.name,
      quantity: scaleQuantity(item.quantity, factor),
      available: fridgeProducts === null ? null : isInFridge(item.name, fridgeProducts),
    })),
    steps: recipe.steps.map((step) => ({
      number: step.number,
      text: step.text,
      imageUrl: step.image_url,
    })),
    sourceUrl: recipe.source_url,
    sourceLabel: sourceLabel(recipe.source_url),
  };
}

/**
 * Recipe card on real data.
 *
 * The page is protected by `RequireAuth`; the token is used for `GET /recipes/{id}` and
 * for the optional fridge request. Portions are local display state: the arithmetic does
 * not need the token and the chosen value is not persisted unless a separate user setting
 * endpoint is added later.
 */
export default function RecipePage() {
  const { token, logout } = useAuth();
  const { recipeId } = useParams<{ recipeId: string }>();
  const [recipe, setRecipe] = useState<RecipeDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fridgeProducts, setFridgeProducts] = useState<string[] | null>(null);
  const [fridgeWarning, setFridgeWarning] = useState<string | null>(null);
  const [baseServings, setBaseServings] = useState<number | null>(null);
  const [selectedServings, setSelectedServings] = useState(1);
  const [baseInput, setBaseInput] = useState('');
  const [servingsInput, setServingsInput] = useState('1');
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(
    async (signal: AbortSignal) => {
      if (!token || !recipeId) {
        return;
      }
      setLoading(true);
      setError(null);
      setFridgeWarning(null);
      try {
        const data = await getRecipe(token, recipeId, signal);
        if (signal.aborted) {
          return;
        }
        setRecipe(data);
        setBaseServings(data.servings);
        setBaseInput(data.servings === null ? '' : String(data.servings));
        setSelectedServings(data.servings ?? 1);
        setServingsInput(String(data.servings ?? 1));

        try {
          const fridge = await listFridgeItems(token, signal);
          if (!signal.aborted) {
            setFridgeProducts(fridge.map((item) => item.product_name));
          }
        } catch (cause) {
          if (signal.aborted) {
            return;
          }
          if (cause instanceof ApiError && cause.status === 401) {
            logout();
            return;
          }
          setFridgeProducts(null);
          setFridgeWarning('Не удалось получить состав холодильника.');
        }
      } catch (cause) {
        if (signal.aborted) {
          return;
        }
        if (cause instanceof ApiError && cause.status === 401) {
          logout();
          return;
        }
        setRecipe(null);
        setError(
          cause instanceof ApiError && cause.status === 404
            ? 'Рецепт не найден'
            : cause instanceof Error
              ? cause.message
              : 'Не удалось загрузить рецепт',
        );
      } finally {
        if (!signal.aborted) {
          setLoading(false);
        }
      }
    },
    [logout, recipeId, token],
  );

  useEffect(() => {
    const controller = new AbortController();
    // Defer one tick for the same reason as the fridge page: no synchronous setState
    // inside the effect, while unmount still aborts the request.
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load, reloadKey]);

  const baseValid = baseServings !== null && baseServings > 0;
  const selectedValid = parsePositiveInt(servingsInput) !== null;
  // While the input is invalid, keep the last valid serving count: the user must not see
  // the ingredients jump back to the source amounts after a mistyped value.
  const factor = baseValid ? selectedServings / baseServings : 1;
  const view = useMemo(
    () =>
      recipe === null
        ? null
        : buildView(recipe, baseValid ? selectedServings : null, factor, fridgeProducts),
    [baseValid, factor, fridgeProducts, recipe, selectedServings],
  );
  const nutrition = useMemo(
    () => scaleNutrition(recipe?.nutrition ?? null, factor, selectedServings),
    [factor, recipe, selectedServings],
  );

  const handleServingsChange = (value: string) => {
    setServingsInput(value);
    const parsed = parsePositiveInt(value);
    if (parsed !== null) {
      setSelectedServings(parsed);
    }
  };

  const handleBaseServingsChange = (value: string) => {
    setBaseInput(value);
    const parsed = parsePositiveInt(value);
    setBaseServings(parsed);
    if (parsed !== null && selectedServings === 1) {
      setSelectedServings(parsed);
      setServingsInput(String(parsed));
    }
  };

  const portionError =
    servingsInput.trim() !== '' && !selectedValid
      ? 'Введите целое положительное число порций'
      : baseInput.trim() !== '' && parsePositiveInt(baseInput) === null
        ? 'Введите целое положительное число порций рецепта'
        : null;

  if (!token) {
    return null;
  }

  if (loading && recipe === null) {
    return (
      <div className={styles.page} data-recipe-id={recipeId}>
        <p className={styles.state} role="status">
          Загружаем рецепт…
        </p>
      </div>
    );
  }

  if (error || view === null) {
    return (
      <div className={styles.page} data-recipe-id={recipeId}>
        <div className={styles.error} role="alert">
          <span>{error ?? 'Рецепт не найден'}</span>
          <button
            type="button"
            className={styles.retry}
            onClick={() => setReloadKey((value) => value + 1)}
          >
            Повторить
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page} data-recipe-id={recipeId}>
      <Breadcrumbs title={view.title} />
      <RecipeHero recipe={view} />

      {fridgeWarning ? <p className={styles.warning}>{fridgeWarning}</p> : null}

      <div className={styles.content}>
        <div className={styles.aside}>
          <PortionControl
            servings={servingsInput}
            baseServings={baseInput}
            needsBaseServings={!baseValid}
            error={portionError}
            disabled={!baseValid}
            onServingsChange={handleServingsChange}
            onBaseServingsChange={handleBaseServingsChange}
          />
          <IngredientsCard recipe={view} />
          <NutritionCard
            nutrition={nutrition}
            source={recipe?.nutrition?.source ?? null}
            servings={selectedServings}
          />
        </div>
        <StepsList steps={view.steps} sourceUrl={view.sourceUrl} sourceLabel={view.sourceLabel} />
      </div>
    </div>
  );
}
