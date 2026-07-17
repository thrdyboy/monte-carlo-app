const BackendUrl = import.meta.env.VITE_BACKEND_URL

export const GetImageUrl = (path: string) => `${BackendUrl}${path}`