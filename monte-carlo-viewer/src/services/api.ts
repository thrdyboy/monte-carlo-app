import type { DataResponse, RunFromExcelRequest, RunSimulationRequest, RunSimulationResponse } from "../types/api";
import axiosInstance from "./axios_service";

export async function runSimulation(data: RunSimulationRequest): Promise<RunSimulationResponse> {
    const res = await axiosInstance.post('/run-simulation', data, {
        headers: {
            'Content-Type': 'application/json'
        }
    })

    return res.data as RunSimulationResponse
}

export async function runFromExcel(data: RunFromExcelRequest): Promise<RunSimulationResponse> {
    const formData = new FormData()
    formData.append('file', data.file)

    const res = await axiosInstance.post('/upload-excel', formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }, params: {
            forecast_years: data.forecast_years
        }
    })
    return res.data as RunSimulationResponse
}

export async function getData(): Promise<DataResponse> {
    const res = await axiosInstance.get('/get-data', {
        headers: {
            'Content-Type': 'application/json'
        }
    })
    return res.data as DataResponse
}