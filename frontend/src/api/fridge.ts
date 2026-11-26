import { apiRequest } from './client';

/** `FridgeItem` of openapi.yaml: one row of `fridge_items`. */
export interface FridgeItem {
  id: number;
  user_id: number;
  product_name: string;
  expiration_date: string;
  quantity: number;
  last_added: string;
}

/** `FridgeItemCreate` of openapi.yaml; the owner is taken from the token. */
export interface FridgeItemInput {
  product_name: string;
  expiration_date: string;
  quantity: number;
}

interface MessageResponse {
  message: string;
}

/** `GET /profile/fridge`: the fridge of the token owner. */
export function listFridgeItems(token: string, signal?: AbortSignal): Promise<FridgeItem[]> {
  return apiRequest<FridgeItem[]>('/profile/fridge?limit=200', { token, signal });
}

/** `POST /profile/fridge`: add one product to the token owner's fridge. */
export function addFridgeItem(token: string, item: FridgeItemInput): Promise<FridgeItem> {
  return apiRequest<FridgeItem>('/profile/fridge', {
    method: 'POST',
    body: item,
    token,
  });
}

/** `DELETE /profile/fridge/{id}`: remove one product of the token owner. */
export function deleteFridgeItem(token: string, id: number): Promise<MessageResponse> {
  return apiRequest<MessageResponse>(`/profile/fridge/${id}`, {
    method: 'DELETE',
    token,
  });
}

/** `DELETE /profile/fridge/expired`: remove only the token owner's expired products. */
export function deleteExpiredFridgeItems(token: string): Promise<MessageResponse> {
  return apiRequest<MessageResponse>('/profile/fridge/expired', {
    method: 'DELETE',
    token,
  });
}
