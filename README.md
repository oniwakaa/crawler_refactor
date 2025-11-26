# B2B Lead Generation Pipeline

[Memory Bank: Active]

A production-ready B2B lead generation system built with **LangExtract** as the core structured-extraction layer, orchestrated by Agno agents and powered by local LLM models via Ollama.

## 🚀 Architecture Overview

```
User Query → Agno Orchestrator → WebNavigator → LangExtract → LeadEnricher → Validator → JSON Output
```

**Key Components:**
- **LangExtract**: Central structured-extraction layer using local/cloud LLMs
- **Agno**: Multi-agent orchestration for pipeline coordination
- **Browser_use**: Real browser automation for content extraction
- **Fallback Strategy**: Local models → Ollama Cloud → Firecrawl API

## 📦 Quick Start

### Prerequisites

```bash
# Install dependencies
pip install agno browser-use ollama langextract pydantic email-validator phonenumbers

# Install and start Ollama (for local models)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull smollm3-thinking
```

### Basic Usage

```python
import asyncio
from src.orchestration.agno_orchestrator import LeadGenOrchestrator

async def generate_leads():
    # Initialize orchestrator
    orchestrator = LeadGenOrchestrator()
    
    # Execute lead generation pipeline
    result = await orchestrator.generate_leads(
        query="SaaS companies in fintech",
        max_companies=10,
        max_people=25
    )
    
    # Access results
    print(f"Generated {len(result.companies)} companies")
    print(f"Generated {len(result.people)} people")
    print(f"Processing time: {result.total_processing_time:.2f}s")
    
    # Save results
    for company in result.companies:
        print(f"Company: {company.company_name}")
        print(f"Website: {company.website_url}")
        print(f"Email: {company.general_email}")
    
    return result

# Run the pipeline
asyncio.run(generate_leads())
```

## 🔧 Configuration

### Model Configuration

```python
from src.extraction.lang_extract_manager import ModelConfig

# Custom model configuration
config = ModelConfig(
    local_model="smollm3-thinking",  # Primary local model
    cloud_model="llama3.1",          # Fallback cloud model
    temperature=0.1,
    max_tokens=2000,
    timeout_seconds=30
)

orchestrator = LeadGenOrchestrator(config={"models": config})
```

### Browser Configuration

```python
# Custom browser settings
browser_config = {
    "headless": True,
    "viewport_size": {"width": 1920, "height": 1080},
    "delay": 2,
    "user_agent": "Mozilla/5.0 (compatible; LeadBot/1.0)"
}

orchestrator = LeadGenOrchestrator(config={"browser": browser_config})
```

## 🏗️ Architecture Components

### 1. LangExtract Manager (`src/extraction/`)

**Core extraction layer with fallback strategy:**

```python
from src.extraction.lang_extract_manager import LangExtractManager

manager = LangExtractManager()

# Extract company data
company_result = await manager.extract_company_data(
    text_content=html_text,
    source_url="https://company.com",
    context_hints=["about page", "contact information"]
)

# Extract person data  
person_result = await manager.extract_person_data(
    text_content=html_text,
    source_url="https://linkedin.com/in/person",
    context_hints=["LinkedIn profile", "professional background"]
)
```

### 2. Browser Navigator (`src/navigation/`)

**Automated web navigation and content extraction:**

```python
from src.navigation.browser_navigator import BrowserNavigator

navigator = BrowserNavigator({"headless": True})

# Navigate to single page
result = await navigator.navigate_to_page("https://company.com")

# Search and extract from multiple results
results = await navigator.search_and_extract("fintech companies San Francisco")

# Find contact pages
contact_pages = await navigator.find_contact_pages("https://company.com")

# Find about pages
about_pages = await navigator.find_about_pages("https://company.com")
```

### 3. Agno Orchestrator (`src/orchestration/`)

**Multi-agent pipeline coordination:**

```python
from src.orchestration.agno_orchestrator import LeadGenOrchestrator

# Initialize pipeline
orchestrator = LeadGenOrchestrator()

# Execute complete pipeline
result = await orchestrator.generate_leads(
    query="AI companies in San Francisco",
    max_companies=20,
    max_people=50
)
```

## 📊 Data Schemas

### Company Profile

```python
from src.extraction.schemas import CompanyProfile

company = CompanyProfile(
    company_name="Acme Corp",
    website_url="https://acme.com",
    description="Enterprise software solutions",
    industry="saas",
    company_size="medium",
    founded_year=2015,
    headquarters_location="San Francisco, CA",
    general_email="info@acme.com",
    general_phone="+1-415-555-0123",
    key_personnel=[person_profile],
    linkedin_url="https://linkedin.com/company/acme",
    tech_stack=["React", "Node.js", "AWS"],
    funding_info="Series B, $50M"
)
```

### Person Profile

```python
from src.extraction.schemas import PersonProfile

person = PersonProfile(
    full_name="John Smith",
    title="CEO",
    company="Acme Corp",
    email="john@acme.com",
    phone="+1-415-555-0124",
    location="San Francisco Bay Area",
    linkedin_url="https://linkedin.com/in/johnsmith",
    twitter_url="https://twitter.com/johnsmith",
    bio="Experienced tech executive with 15+ years in SaaS",
    years_experience=15,
    skills=["Leadership", "SaaS", "Fundraising"]
)
```

## 🧪 Testing

Run comprehensive integration tests:

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_langextract_integration.py -v
pytest tests/test_langextract_integration.py::TestLangExtractManager -v

# Run real-world integration tests
pytest tests/ -m integration -v

# Run smoke tests only
pytest tests/ -m "not integration" -v
```

### Test Data

The testing framework uses real websites and actual model inference to ensure production reliability:

```python
# Example from test suite
result = await extract_manager.extract_company_data(
    text_content=stripe_html_content,
    source_url="https://stripe.com",
    context_hints=["company homepage"]
)

assert result.success
assert result.data.company_name == "Stripe"
assert result.confidence_score > 0.5
```

## 🔄 Extraction Flow

1. **Navigation**: Browser_use navigates and extracts clean text content
2. **Primary Extraction**: LangExtract with local Ollama models (smollm3-thinking)
3. **Fallback 1**: LangExtract with Ollama Cloud models (llama3.1)
4. **Fallback 2**: Firecrawl API for structured extraction
5. **Enrichment**: Cross-reference and enhance extracted data
6. **Validation**: Validate emails, phones, URLs, and quality scores
7. **Output**: Return structured CompanyProfile/PersonProfile objects

## 🎯 Usage Examples

### Example 1: Company Lead Generation

```python
async def find_saas_companies():
    orchestrator = LeadGenOrchestrator()
    
    result = await orchestrator.generate_leads(
        query="SaaS companies enterprise software California",
        max_companies=15,
        max_people=5  # Focus on companies rather than individuals
    )
    
    for company in result.companies:
        print(f"📊 {company.company_name}")
        print(f"   🌐 {company.website_url}")
        print(f"   📧 {company.general_email}")
        print(f"   🏢 {company.industry.value} - {company.company_size.value}")
        print(f"   🎯 Confidence: {company.extraction_confidence:.2f}")
        print()
```

### Example 2: Executive Contact Discovery

```python
async def find_executives():
    orchestrator = LeadGenOrchestrator()
    
    result = await orchestrator.generate_leads(
        query="CTO VP Engineering fintech companies",
        max_companies=5,
        max_people=20  # Focus on individual contacts
    )
    
    for person in result.people:
        if person.title and any(title in person.title.lower() 
                               for title in ['cto', 'vp', 'chief', 'head']):
            print(f"👤 {person.full_name}")
            print(f"   💼 {person.title} at {person.company}")
            print(f"   📧 {person.email}")
            print(f"   📍 {person.location}")
            print()
```

### Example 3: Contact Page Mining

```python
async def mine_contact_pages():
    navigator = BrowserNavigator()
    
    # Find contact pages for specific companies
    urls = [
        "https://stripe.com",
        "https://vercel.com", 
        "https://linear.app"
    ]
    
    for url in urls:
        contact_pages = await navigator.find_contact_pages(url)
        for page in contact_pages:
            print(f"Found contact page: {page.url}")
            print(f"Content preview: {page.content[:200]}...")
            
            # Extract contact info
            manager = LangExtractManager()
            result = await manager.extract_company_data(
                page.content, 
                page.url,
                context_hints=["contact page"]
            )
            
            if result.success and result.data:
                contact = result.data
                print(f"Contact: {contact.general_email}")
                print(f"Phone: {contact.general_phone}")
            print("-" * 50)
```

## 🔧 Advanced Configuration

### Custom Extraction Prompts

```python
from src.extraction.prompts import ExtractionPrompts

# Custom company prompt
custom_prompt = ExtractionPrompts.get_company_prompt(
    text_content=html_content,
    context_hints=["enterprise sales page", "B2B focused"],
    custom_instructions="Prioritize enterprise customers and pricing information"
)

# Custom person prompt  
custom_prompt = ExtractionPrompts.get_person_prompt(
    text_content=html_content,
    context_hints=["team page", "leadership"],
    custom_instructions="Focus on C-level executives and decision makers"
)
```

### Batch Processing

```python
async def process_multiple_queries():
    queries = [
        "SaaS companies Series B funding",
        "Fintech startups San Francisco", 
        "Enterprise software CTO contacts"
    ]
    
    all_results = []
    for query in queries:
        result = await orchestrator.generate_leads(query, max_companies=5)
        all_results.append(result)
        
    # Consolidate results
    all_companies = []
    all_people = []
    for result in all_results:
        all_companies.extend(result.companies)
        all_people.extend(result.people)
        
    return all_companies, all_people
```

## 📈 Performance & Monitoring

### Extraction Statistics

```python
result = await orchestrator.generate_leads("query", max_companies=10)

# Access detailed statistics
stats = result.extraction_stats
print(f"Total extractions: {stats['total_extractions']}")
print(f"Successful extractions: {stats['successful_extractions']}")
print(f"Average confidence: {stats['average_confidence']:.2f}")

# Validation report
validation = stats['validation_report']
print(f"Quality score: {validation['overall_quality_score']:.2f}")
print(f"Company validation: {validation['companies']['valid']}/{validation['companies']['total']}")
print(f"Person validation: {validation['people']['valid']}/{validation['people']['total']}")
```

### Processing Time Monitoring

```python
import time

start_time = time.time()
result = await orchestrator.generate_leads("complex query")
end_time = time.time()

print(f"Total pipeline time: {end_time - start_time:.2f}s")
print(f"Reported processing time: {result.total_processing_time:.2f}s")
```

## 🚦 Error Handling

```python
try:
    result = await orchestrator.generate_leads("query")
    
    if not result.success:
        print("Pipeline failed:")
        for error in result.errors:
            print(f"  - {error}")
    
    # Check individual component success
    if result.companies:
        print(f"Successfully extracted {len(result.companies)} companies")
    else:
        print("No company data extracted")
        
    if result.people:
        print(f"Successfully extracted {len(result.people)} people")
    else:
        print("No person data extracted")
        
except Exception as e:
    print(f"Pipeline exception: {e}")
```

## 🔒 Data Validation

The pipeline includes comprehensive validation:

- **Email validation**: Format checking and business relevance
- **Phone validation**: International format standardization
- **URL validation**: Website URL verification
- **Confidence scoring**: Extraction quality assessment
- **Duplicate detection**: Remove redundant entries
- **Data consistency**: Cross-reference validation

## 📚 Memory Bank Integration

This project uses a memory bank system for persistent context:

- **Architecture decisions**: Documented in `.kilocode/rules/memory-bank/`
- **Technology updates**: Tracked in `techContext.md`
- **Active tasks**: Maintained in `activeContext.md`
- **Testing philosophy**: Defined in `testing.md`

## 🤝 Contributing

1. Follow the testing principle: "fail real and loud, or succeed real and loud"
2. All tests must use actual scripts and real-world scenarios
3. Update memory bank files when making significant changes
4. Ensure backward compatibility with existing schemas

## 📄 License

This project is licensed under the MIT License.