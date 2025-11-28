# Code Review Assistant - MVP Specification

## 🎯 MVP Goal

Create a **"magical first experience"** where a developer pastes code and gets intelligent, specific feedback in under 30 seconds. Focus on the core backend that makes users think "wow, this AI really understands my code."

## 🔥 The Magic Moment

**User Experience**:
1. Paste code into a simple text area
2. Click "Review Code"
3. Get back detailed, actionable feedback with specific line references and improvement suggestions
4. Feel like they have an expert developer looking over their shoulder

## 🏗️ MVP Architecture

**Stack**: Python + FastAPI + Anthropic Claude API
**Deployment**: Railway (single service)
**Frontend**: Minimal HTML/CSS/JS (no React complexity for MVP)
**Data**: Stateless, no database

## ✨ Core Features (MVP)

### 1. Single Code Analysis Endpoint
```
POST /api/analyze
{
  "code": "def calculate_total(items):\n    total = 0\n    for item in items...",
  "language": "python"  // optional, auto-detect if not provided
}
```

**Response**:
```json
{
  "analysis": {
    "overall_score": 7.5,
    "issues": [
      {
        "type": "performance",
        "severity": "medium",
        "line": 3,
        "message": "Consider using sum() builtin instead of manual loop",
        "suggestion": "return sum(item.price for item in items)",
        "explanation": "Built-in sum() is more Pythonic and potentially faster"
      }
    ],
    "suggestions": [...],
    "summary": "Good code structure with opportunities for optimization"
  }
}
```

### 2. Language Auto-Detection
- Analyze code patterns, syntax, keywords
- Support: Python, JavaScript, TypeScript, Java, Go
- Fallback to generic analysis if language unclear

### 3. Claude-Powered Analysis
**Smart Prompt Engineering**:
- Include code with line numbers
- Ask for specific categories: security, performance, style, bugs
- Request line-specific feedback with explanations
- Get concrete improvement suggestions

### 4. Intelligent Categorization
**Issue Types**:
- 🔴 **Critical**: Security vulnerabilities, bugs
- 🟡 **Important**: Performance issues, bad practices
- 🔵 **Style**: Naming, formatting, minor improvements
- 💡 **Suggestions**: Best practices, modern patterns

## 🧠 Claude Integration Strategy

### Prompt Template
```
You are an expert code reviewer. Analyze this {language} code and provide specific, actionable feedback.

Code (with line numbers):
{numbered_code}

Please provide:
1. Critical issues (security, bugs) - be specific about risks
2. Performance improvements - suggest concrete optimizations
3. Code quality issues - naming, structure, readability
4. Best practice suggestions - modern patterns, conventions

For each issue:
- Reference specific line numbers
- Explain WHY it's problematic
- Provide concrete improvement suggestions
- Rate severity: critical/important/minor

Focus on being helpful and educational, not just critical.
```

### Response Processing
- Parse Claude's response into structured JSON
- Extract line references automatically
- Categorize issues by type and severity
- Generate overall code quality score

## 🚀 MVP Backend Implementation

### FastAPI App Structure
```
app/
├── main.py              # FastAPI app, single endpoint
├── analyzer.py          # Claude API integration
├── language_detector.py # Auto-detect programming language
├── response_parser.py   # Parse Claude response to JSON
└── prompts.py          # Prompt templates
```

### Key Components

#### 1. Main API Endpoint
```python
@app.post("/api/analyze")
async def analyze_code(request: CodeAnalysisRequest):
    # 1. Detect language if not provided
    # 2. Add line numbers to code
    # 3. Generate Claude prompt
    # 4. Call Claude API
    # 5. Parse response to structured format
    # 6. Return analysis results
```

#### 2. Language Detection
- Regex patterns for syntax detection
- File extension hints (if provided)
- Keyword analysis for disambiguation
- Confidence scoring

#### 3. Claude API Client
- Async HTTP client for API calls
- Smart retry logic with exponential backoff
- Token counting and optimization
- Error handling and fallbacks

#### 4. Response Parser
- Extract issues from Claude's natural language response
- Map to structured format with line numbers
- Generate severity scores
- Create summary statistics

## 🎨 Minimal Frontend (MVP)

Simple single-page interface:
- Large code textarea with syntax highlighting
- Language selector dropdown
- "Analyze Code" button with loading state
- Results display with collapsible sections
- Copy-to-clipboard for suggestions

## 📊 Success Metrics (MVP)

### Technical
- ✅ Analysis completes in <30 seconds
- ✅ 95%+ successful Claude API responses
- ✅ Accurate language detection >90%
- ✅ Structured, actionable feedback format

### User Experience
- ✅ Users get specific, line-referenced feedback
- ✅ Suggestions feel intelligent and relevant
- ✅ Interface is intuitive (no learning curve)
- ✅ Results are actionable and educational

## 🔧 Implementation Priority

### Phase 1: Core Engine (Week 1)
1. FastAPI setup with single analyze endpoint
2. Claude API integration with basic prompts
3. Language detection for Python/JavaScript
4. Response parsing to JSON structure

### Phase 2: Intelligence (Week 2)
1. Advanced prompt engineering for better feedback
2. Multi-language support (add TypeScript, Java, Go)
3. Response quality improvements
4. Error handling and edge cases

### Phase 3: Polish (Week 3)
1. Minimal but clean frontend interface
2. Railway deployment configuration
3. Performance optimization
4. User testing and feedback integration

## 🎯 The "Magic" Elements

### 1. Specific Line References
Not just "improve variable naming" but "Line 15: Consider renaming 'data' to 'user_profiles' for clarity"

### 2. Concrete Suggestions
Not just "optimize performance" but "Replace the nested loop (lines 23-27) with: `result = {k: v for item in items for k, v in item.items()}`"

### 3. Educational Explanations
Not just what to change, but why: "This creates unnecessary O(n²) complexity because..."

### 4. Contextual Awareness
Understanding the code's purpose and suggesting improvements that fit the context

## 🚫 MVP Exclusions (Save for Later)

- File upload (paste-only for MVP)
- Git repository analysis
- User accounts/history
- Custom rule configuration
- Multiple output formats
- Batch processing
- Advanced frontend frameworks
- Database storage
- Team features

## ✅ MVP Definition of Done

The MVP is complete when:
1. ✅ Developer can paste any supported code and get intelligent feedback in <30s
2. ✅ Feedback includes specific line references and concrete suggestions
3. ✅ Language detection works reliably for 5+ languages
4. ✅ Claude integration provides consistently valuable insights
5. ✅ Simple frontend makes the experience feel polished
6. ✅ Deployed on Railway and accessible via web
7. ✅ Error handling gracefully manages edge cases

**Success Indicator**: When users paste their code and immediately think *"This is incredibly helpful - how did it know exactly what to improve?"*

The MVP focuses on nailing the core magical experience: paste code → get brilliant feedback. Everything else is secondary.