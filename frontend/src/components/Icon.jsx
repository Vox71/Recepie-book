const paths = {
  sprout: <><path d="M12 21v-9M5 21h14"/><path d="M12 15C5 15 3 11 3 6c6 0 9 3 9 9ZM12 11c0-6 3-9 9-9 0 6-3 9-9 9Z"/></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
  heart: <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5h4"/></>,
  fridge: <><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M5 9h14M9 5v1M9 12v3"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6"/>,
  plus: <path d="M12 5v14M5 12h14"/>,
  chef: <><path d="M6 14a5 5 0 0 1-1-9 5 5 0 0 1 9-2 5 5 0 0 1 5 9v9H6Z"/><path d="M6 17h13"/></>,
  leaf: <><path d="M20 3C10 2 3 6 4 13s16 7 16-10Z"/><path d="M3 21 16 8"/></>,
  egg: <path d="M19 14c0 5-3 8-7 8s-7-3-7-8S8 2 12 2s7 7 7 12Z"/>,
  wheat: <><path d="M3 21 21 3M8 16c-5 0-7-3-5-6 4 0 6 2 5 6Zm4-4C7 12 5 9 7 6c4 0 6 2 5 6Zm4-4c-3-2-3-5 0-7 4 2 4 5 0 7ZM8 16c0 5 3 7 6 5 0-4-2-6-6-5Zm4-4c0 5 3 7 6 5 0-4-2-6-6-5Z"/></>,
  bottle: <><path d="M9 2h6M10 2v5l-3 4v11h10V11l-3-4V2M7 13h10"/></>,
  check: <><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></>,
  users: <><circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M17 4a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 4v3"/></>,
  eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
  eyeOff: <><path d="m3 3 18 18M10 5a12 12 0 0 1 12 7 19 19 0 0 1-3 4M6 6a19 19 0 0 0-4 6s4 7 10 7a12 12 0 0 0 5-1M10 10a3 3 0 0 0 4 4"/></>,
  image: <><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1"/><path d="m3 17 6-6 4 4 3-3 5 5"/></>,
}

export default function Icon({ name, size = 20 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
