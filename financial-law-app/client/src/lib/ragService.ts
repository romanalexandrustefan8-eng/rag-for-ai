/**
 * RAG (Retrieval-Augmented Generation) Service
 * 
 * This module provides connectors for integrating with RAG models
 * to fetch and summarize financial laws.
 * 
 * Configuration:
 * - RAG_API_URL: Base URL of your RAG API endpoint
 * - RAG_API_KEY: Authentication key for RAG API
 * 
 * Example usage:
 * const summary = await ragService.summarizeLaw(lawText, 'romanian');
 */

export interface LawSummary {
  title: string;
  simplified: string;
  keyPoints: string[];
  applicableTo: string[];
  deadline: string | null;
  source: string;
}

export interface RAGRequest {
  lawText: string;
  language: 'romanian' | 'english';
  format: 'simplified' | 'detailed';
}

export interface RAGResponse {
  summary: LawSummary;
  confidence: number;
  timestamp: string;
}

class RAGService {
  private apiUrl: string;
  private apiKey: string;
  private timeout: number = 30000; // 30 seconds

  constructor() {
    // These can be set via environment variables
    this.apiUrl = import.meta.env.VITE_RAG_API_URL || 'https://api.example.com/rag';
    this.apiKey = import.meta.env.VITE_RAG_API_KEY || '';
  }

  /**
   * Set custom RAG API configuration
   */
  setConfig(apiUrl: string, apiKey: string) {
    this.apiUrl = apiUrl;
    this.apiKey = apiKey;
  }

  /**
   * Summarize a financial law using RAG model
   */
  async summarizeLaw(lawText: string, language: 'romanian' | 'english' = 'romanian'): Promise<LawSummary> {
    try {
      const request: RAGRequest = {
        lawText,
        language,
        format: 'simplified',
      };

      const response = await this.fetchWithTimeout(
        `${this.apiUrl}/summarize`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(this.apiKey && { 'Authorization': `Bearer ${this.apiKey}` }),
          },
          body: JSON.stringify(request),
        }
      );

      if (!response.ok) {
        throw new Error(`RAG API error: ${response.statusText}`);
      }

      const data: RAGResponse = await response.json();
      return data.summary;
    } catch (error) {
      console.error('RAG summarization failed:', error);
      // Return a fallback summary if RAG fails
      return this.getFallbackSummary(lawText);
    }
  }

  /**
   * Extract key points from a law
   */
  async extractKeyPoints(lawText: string, language: 'romanian' | 'english' = 'romanian'): Promise<string[]> {
    try {
      const response = await this.fetchWithTimeout(
        `${this.apiUrl}/extract-key-points`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(this.apiKey && { 'Authorization': `Bearer ${this.apiKey}` }),
          },
          body: JSON.stringify({ lawText, language }),
        }
      );

      if (!response.ok) {
        throw new Error(`RAG API error: ${response.statusText}`);
      }

      const data = await response.json();
      return data.keyPoints || [];
    } catch (error) {
      console.error('Key point extraction failed:', error);
      return [];
    }
  }

  /**
   * Get applicable entities for a law
   */
  async getApplicableEntities(lawText: string, language: 'romanian' | 'english' = 'romanian'): Promise<string[]> {
    try {
      const response = await this.fetchWithTimeout(
        `${this.apiUrl}/applicable-entities`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(this.apiKey && { 'Authorization': `Bearer ${this.apiKey}` }),
          },
          body: JSON.stringify({ lawText, language }),
        }
      );

      if (!response.ok) {
        throw new Error(`RAG API error: ${response.statusText}`);
      }

      const data = await response.json();
      return data.applicableEntities || [];
    } catch (error) {
      console.error('Applicable entities extraction failed:', error);
      return [];
    }
  }

  /**
   * Fetch with timeout
   */
  private fetchWithTimeout(url: string, options: RequestInit): Promise<Response> {
    return Promise.race([
      fetch(url, options),
      new Promise<Response>((_, reject) =>
        setTimeout(() => reject(new Error('RAG API request timeout')), this.timeout)
      ),
    ]);
  }

  /**
   * Fallback summary when RAG API is unavailable
   */
  private getFallbackSummary(lawText: string): LawSummary {
    // Extract first 200 characters as simplified version
    const simplified = lawText.substring(0, 200).trim() + '...';
    
    return {
      title: 'Rezumat Lege',
      simplified,
      keyPoints: ['Consultați textul complet pentru detalii complete'],
      applicableTo: ['Instituții financiare'],
      deadline: null,
      source: 'Fallback',
    };
  }
}

// Export singleton instance
export const ragService = new RAGService();

// Export class for testing
export default RAGService;
