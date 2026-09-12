import axios, { AxiosError } from "axios";
import type { ApiError } from "../types/api";

const axiosInstance = axios.create({
    baseURL: "/api",
    withCredentials: true,
    timeout: 30_000
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
    (error: AxiosError) => {
        let normalized: ApiError = {
            status: 0,
            message: error.message,
            raw: error
        }

        if (error.response) {
            const status = error.response.status
            const data = error.response.data as { detail: any }

            let detail = data?.detail
            if (Array.isArray(detail)) {
                detail = detail
                    .map((d: { loc: any; msg: any }) => `${d.loc.join('.')}: ${d.msg}`)
                    .join(', ')
            }

            normalized = {
                status,
                message: detail || error.response.statusText || `HTTP ${status}`,
                raw: error
            }
        }

        if (import.meta.env.DEV) {
            console.error(`API Error [${normalized.status}]: `, normalized.message)
        }

        return Promise.reject(normalized)
    }
)

export default axiosInstance