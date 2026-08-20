const BackendUrl = import.meta.env.VITE_BACKEND_URL as string

export const GetImageUrl = (path: string) => `${BackendUrl}${path}`