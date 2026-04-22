# RAG Model Integration Guide

## Overview

This financial law app includes connectors for integrating with RAG (Retrieval-Augmented Generation) models to automatically generate simplified summaries of financial laws.

## Architecture

The RAG integration consists of three main components:

### 1. RAG Service (`client/src/lib/ragService.ts`)

The core service that handles communication with your RAG API endpoint.

**Key Methods:**
- `summarizeLaw(lawText, language)` - Generate a simplified summary of a law
- `extractKeyPoints(lawText, language)` - Extract key points from a law
- `getApplicableEntities(lawText, language)` - Identify who the law applies to
- `setConfig(apiUrl, apiKey)` - Configure custom API endpoint

**Supported Languages:**
- `romanian` (default)
- `english`

### 2. React Hook (`client/src/hooks/useRagSummary.ts`)

A custom React hook that wraps the RAG service for easy integration in components.

**Usage:**
```tsx
const { summary, loading, error, refetch } = useRagSummary(lawText, 'romanian');

if (loading) return <div>Loading summary...</div>;
if (error) return <div>Error: {error}</div>;

return <div>{summary?.simplified}</div>;
```

### 3. LawCard Component (`client/src/components/LawCard.tsx`)

The UI component that displays laws with RAG-generated summaries.

**Features:**
- Automatic summary generation on component mount
- Loading state with spinner
- Fallback content if RAG API is unavailable
- Expandable full text view
- Key points display
- Applicable entities display
- Deadline information

## Configuration

### Environment Variables

Set these environment variables in your `.env` file:

```env
# RAG API Configuration
VITE_RAG_API_URL=https://your-rag-api.com/api
VITE_RAG_API_KEY=your-api-key-here
```

### Runtime Configuration

You can also configure the RAG service at runtime:

```tsx
import { ragService } from '@/lib/ragService';

ragService.setConfig(
  'https://your-rag-api.com/api',
  'your-api-key-here'
);
```

## API Endpoint Specification

Your RAG API should implement the following endpoints:

### 1. Summarize Endpoint

**POST** `/summarize`

**Request Body:**
```json
{
  "lawText": "Full text of the law...",
  "language": "romanian",
  "format": "simplified"
}
```

**Response:**
```json
{
  "summary": {
    "title": "Law Title",
    "simplified": "Simplified explanation in 2-3 sentences...",
    "keyPoints": [
      "Key point 1",
      "Key point 2",
      "Key point 3"
    ],
    "applicableTo": [
      "Banks",
      "Financial Institutions",
      "Payment Service Providers"
    ],
    "deadline": "2024-12-31",
    "source": "Official Gazette"
  },
  "confidence": 0.95,
  "timestamp": "2024-04-22T18:00:00Z"
}
```

### 2. Extract Key Points Endpoint

**POST** `/extract-key-points`

**Request Body:**
```json
{
  "lawText": "Full text of the law...",
  "language": "romanian"
}
```

**Response:**
```json
{
  "keyPoints": [
    "Key point 1",
    "Key point 2",
    "Key point 3"
  ]
}
```

### 3. Applicable Entities Endpoint

**POST** `/applicable-entities`

**Request Body:**
```json
{
  "lawText": "Full text of the law...",
  "language": "romanian"
}
```

**Response:**
```json
{
  "applicableEntities": [
    "Banks",
    "Financial Institutions",
    "Payment Service Providers"
  ]
}
```

## Error Handling

The RAG service includes graceful error handling:

1. **API Timeout**: If the RAG API doesn't respond within 30 seconds, a fallback summary is returned
2. **API Error**: If the API returns an error status, the component displays a fallback message
3. **Network Error**: If there's no network connection, the component shows "Consultați textul complet pentru detalii"

## Integration Examples

### Example 1: Using the Hook in a Custom Component

```tsx
import { useRagSummary } from '@/hooks/useRagSummary';

export function MyLawComponent({ lawText }) {
  const { summary, loading } = useRagSummary(lawText, 'romanian');

  return (
    <div>
      {loading ? (
        <p>Generating summary...</p>
      ) : (
        <p>{summary?.simplified}</p>
      )}
    </div>
  );
}
```

### Example 2: Direct Service Usage

```tsx
import { ragService } from '@/lib/ragService';

async function generateSummary(lawText) {
  try {
    const summary = await ragService.summarizeLaw(lawText, 'romanian');
    console.log('Summary:', summary.simplified);
  } catch (error) {
    console.error('Failed to generate summary:', error);
  }
}
```

### Example 3: Batch Processing

```tsx
import { ragService } from '@/lib/ragService';

async function processManyLaws(laws) {
  const summaries = await Promise.all(
    laws.map(law => ragService.summarizeLaw(law.text, 'romanian'))
  );
  return summaries;
}
```

## Testing Without a Real RAG API

For development and testing, the app includes a fallback mechanism. If you don't have a RAG API configured:

1. Summaries will be generated from the first 200 characters of the law text
2. Key points will show a placeholder message
3. Applicable entities will default to "Instituții financiare"

To test with mock data, you can modify the `ragService.ts` to return test summaries:

```tsx
// In ragService.ts
private getFallbackSummary(lawText: string): LawSummary {
  return {
    title: 'Test Summary',
    simplified: 'This is a test summary for development purposes.',
    keyPoints: ['Test point 1', 'Test point 2'],
    applicableTo: ['Test Entity'],
    deadline: '2024-12-31',
    source: 'Test',
  };
}
```

## Performance Considerations

1. **Caching**: Consider implementing caching in your RAG API to avoid re-summarizing the same laws
2. **Rate Limiting**: Implement rate limiting to prevent abuse
3. **Async Loading**: Summaries load asynchronously, so the UI remains responsive
4. **Timeout**: The default timeout is 30 seconds; adjust in `ragService.ts` if needed

## Troubleshooting

### Summaries not appearing

1. Check that `VITE_RAG_API_URL` is set correctly
2. Verify the RAG API is running and accessible
3. Check browser console for error messages
4. Ensure the API response matches the expected format

### Slow performance

1. Check network latency to the RAG API
2. Increase the timeout value in `ragService.ts` if needed
3. Consider implementing caching in your RAG API

### API authentication issues

1. Verify `VITE_RAG_API_KEY` is set correctly
2. Check that the API key has the necessary permissions
3. Ensure the Authorization header format is correct

## Future Enhancements

Potential improvements to the RAG integration:

1. **Caching Layer**: Add local caching to reduce API calls
2. **Batch Summarization**: Support batch processing of multiple laws
3. **Custom Prompts**: Allow customizing the summarization prompt
4. **Multi-language Support**: Extend to more languages
5. **Confidence Scoring**: Display confidence scores for summaries
6. **User Feedback**: Allow users to rate summary quality
7. **Streaming Responses**: Support streaming for faster perceived performance
