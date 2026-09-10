import axiosInstance from "../services/axios_service"

const BackendUrl = axiosInstance.defaults.baseURL as string

export const GetImageUrl = (path: string) => `${BackendUrl}${path}`