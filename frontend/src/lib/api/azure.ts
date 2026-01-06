
export interface SearchRequest {
    query: string;
    max_results?: number;
    country?: string;
    user_id: string;
}

export interface SearchResponse {
    job_id: string;
    status: string;
    note?: string;
    error?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const AzureService = {
    async startSearch(request: SearchRequest): Promise<SearchResponse> {
        const response = await fetch(`${API_URL}/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.statusText}`);
        }

        return response.json();
    },

    async getJobStatus(jobId: string): Promise<any> {
        const response = await fetch(`${API_URL}/jobs/${jobId}`);
        if (!response.ok) {
            throw new Error(`API error: ${response.statusText}`);
        }
        return response.json();
    }
};
