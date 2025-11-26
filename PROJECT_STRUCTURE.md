# Project Structure

[Memory Bank: Active]

This document provides an overview of the refactored B2B Lead Generation architecture using LangExtract as the core extraction layer.

## 🏗️ Directory Structure

```
/Users/carlo/Desktop/pr_prj/crw_ref
├── .kilocode/rules/memory-bank/          # Memory bank system for persistent context
│   ├── brief.md                          # Project vision & business objectives
│   ├── architecture.md                   # Technical architecture documentation
│   ├── techContext.md                    # Technology stack and dependencies
│   ├── activeContext.md                  # Current status and recent decisions
│   ├── memory-bank-rules.md              # Memory bank usage guidelines
│   └── testing.md                        # Testing philosophy and guidelines
├── src/                                  # Core source code
│   ├── extraction/                       # LangExtract-based extraction layer
│   │   ├── schemas.py                    # Pydantic schemas (CompanyProfile, PersonProfile)
│   │   ├── lang_extract_manager.py       # Core LangExtract integration with fallback
│   │   └── prompts.py                    # Optimized prompts for different models
│   ├── navigation/                       # Browser navigation and content extraction
│   │   └── browser_navigator.py          # Browser_use integration agent
│   └── orchestration/                    # Agno-based multi-agent orchestration
│       └── agno_orchestrator.py          # Main pipeline coordinator
├── tests/                                # Comprehensive test suite
│   └── test_langextract_integration.py   # Real-world integration tests
├── examples/                             # Usage examples and demos
│   └── lead_generation_example.py        # Complete usage examples
└── README.md                             # Main documentation and quick start
```

## 🔄 Architecture Flow

```
User Query → Agno Orchestrator → WebNavigator → LangExtract → LeadEnricher → Validator → JSON Output
     ↓              ↓                  ↓             ↓            ↓            ↓
Query Parsing   Agent Coordination   Browser     Extraction    Data         Validation
  & Routing      & Task Management   Automation   Layer       Enrichment   & QC
```

### Core Components

#### 1. **Extraction Layer** (`src/extraction/`)
- **LangExtract Manager**: Handles structured extraction with fallback strategy
- **Schemas**: Pydantic models for CompanyProfile and PersonProfile
- **Prompts**: Optimized prompts for different model types (SmolLM3, Llama)

#### 2. **Navigation Layer** (`src/navigation/`)
- **Browser Navigator**: Real browser automation using browser_use
- **Content Discovery**: Automated finding of contact pages, about pages
- **HTML Processing**: Clean text extraction and preprocessing

#### 3. **Orchestration Layer** (`src/orchestration/`)
- **Agno Agents**: WebNavigator, ContentExtractor, LeadEnricher, ValidationAgent
- **Pipeline Coordination**: Multi-stage workflow management
- **Error Handling**: Robust fallback and recovery mechanisms

## 🎯 Key Features

### LangExtract Integration
- **Primary**: Local Ollama models (smollm3-thinking) for cost efficiency
- **Fallback 1**: Ollama Cloud models (llama3.1) for complex pages
- **Fallback 2**: Firecrawl API for structured extraction

### Agent Architecture
- **WebNavigator**: Browser automation and content discovery
- **ContentExtractor**: LangExtract-powered structured data extraction
- **LeadEnricher**: Data enhancement and cross-referencing
- **ValidationAgent**: Quality assurance and validation

### Data Schemas
- **CompanyProfile**: Comprehensive company information structure
- **PersonProfile**: Individual contact and professional information
- **ExtractionResult**: Wrapper with metadata and confidence scoring

## 🧪 Testing Philosophy

Following the "fail real and loud, or succeed real and loud" principle:
- Real websites and actual model inference
- No mock data or artificial stubs
- Production-level validation and error handling
- Integration tests with live pipelines

## 🚀 Quick Start

1. **Install Dependencies**:
   ```bash
   pip install agno browser-use ollama langextract pydantic
   ```

2. **Setup Local Models**:
   ```bash
   ollama pull smollm3-thinking
   ```

3. **Run Basic Example**:
   ```python
   from src.orchestration.agno_orchestrator import LeadGenOrchestrator
   
   orchestrator = LeadGenOrchestrator()
   result = await orchestrator.generate_leads(
       query="SaaS companies San Francisco",
       max_companies=10,
       max_people=25
   )
   ```

4. **Run Tests**:
   ```bash
   pytest tests/ -v
   ```

## 📊 Key Metrics

The system tracks comprehensive metrics:
- **Extraction Success Rate**: Percentage of successful extractions
- **Confidence Scoring**: Quality assessment of extracted data
- **Processing Time**: End-to-end pipeline timing
- **Fallback Usage**: Effectiveness of fallback strategies
- **Data Quality**: Validation scores and error rates

## 🔧 Configuration Options

### Model Configuration
- Local model selection (smollm3-thinking, qwen, etc.)
- Cloud model fallback (llama3.1, gpt-4, etc.)
- Token limits and temperature settings
- Timeout configurations

### Browser Configuration
- Headless/headed mode
- Viewport and user agent settings
- Navigation delays and timeouts
- Custom user agent strings

### Pipeline Configuration
- Maximum companies/people to extract
- Processing batch sizes
- Validation strictness levels
- Output format customization

## 🔄 Migration from ScrapeGraphAI

This refactoring completely removes ScrapeGraphAI dependency:
- **Removed**: ScrapeGraphAI extraction layer
- **Replaced with**: LangExtract as primary structured extraction
- **Enhanced**: Agent orchestration with Agno
- **Improved**: Local model integration with Ollama
- **Added**: Comprehensive fallback strategies

## 📈 Performance Characteristics

- **Cost Efficiency**: Primary usage of local models reduces API costs
- **Scalability**: Parallel processing and batch operations
- **Reliability**: Multi-tier fallback ensures high success rates
- **Quality**: Confidence scoring and validation at each stage
- **Flexibility**: Configurable for different use cases and requirements

## 🛡️ Error Handling & Resilience

- **Graceful Degradation**: Fallback through extraction methods
- **Timeout Management**: Configurable timeouts for all operations
- **Network Resilience**: Robust handling of connectivity issues
- **Data Validation**: Comprehensive validation at multiple stages
- **Logging & Monitoring**: Detailed logging for debugging and optimization

This architecture provides a robust, scalable, and cost-effective solution for B2B lead generation using modern LLM-based extraction techniques.