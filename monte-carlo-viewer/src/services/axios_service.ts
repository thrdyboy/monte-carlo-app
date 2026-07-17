import axios, { AxiosError } from "axios";

const axiosInstance = axios.create({
    baseURL: import.meta.env.VITE_BACKEND_URL,
    withCredentials: true
})

axiosInstance.interceptors.request.use(
    (config) => {
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

axiosInstance.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error instanceof AxiosError) {
            console.error("API Error: ", error.response?.data || error.message)
        }
        return Promise.reject(error)
    }
)

export default axiosInstance