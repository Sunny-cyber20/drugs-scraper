import requests
from bs4 import BeautifulSoup
import time
from pathlib import Path

def discover_drug_urls():
    """Discover all drug URLs from Drugs.com using alpha pages"""
    
    base_url = "https://www.drugs.com"
    all_urls = set()
    
    # Letters A through K
    letters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k']
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    print("\n🔍 Discovering drug URLs from Drugs.com alpha pages...\n")
    
    for letter in letters:
        try:
            # CORRECT URL format: /alpha/a.html
            url = f"{base_url}/alpha/{letter}.html"
            print(f"📥 Fetching letter {letter.upper()}: {url}")
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all drug links
            drug_links = soup.find_all('a', href=True)
            letter_count = 0
            
            for link in drug_links:
                href = link['href']
                
                # Filter for drug pages (pattern: /drugname.html)
                if href.endswith('.html') and not href.startswith('http'):
                    # Skip non-drug pages
                    skip_keywords = ['alpha', 'search', 'admin', 'professional', 'condition']
                    if not any(x in href.lower() for x in skip_keywords):
                        full_url = f"{base_url}{href}" if not href.startswith('/') else f"{base_url}{href}"
                        all_urls.add(full_url)
                        letter_count += 1
            
            print(f"   ✅ Found {letter_count} drugs\n")
            time.sleep(1)  # Be respectful to the server
            
        except Exception as e:
            print(f"   ⚠️ Error: {str(e)}\n")
            continue
    
    return all_urls

def save_urls(urls):
    """Save discovered URLs to file"""
    # Create data directory if it doesn't exist
    Path("data").mkdir(exist_ok=True)
    
    output_file = "data/candidate_urls.txt"
    
    with open(output_file, 'w') as f:
        for url in sorted(urls):
            f.write(url + '\n')
    
    print(f"\n{'='*70}")
    print(f"✅ Successfully discovered {len(urls)} drug URLs!")
    print(f"📁 Saved to: {output_file}")
    print(f"{'='*70}\n")
    
    return len(urls)

if __name__ == '__main__':
    print("\n" + "="*70)
    print("DRUGS.COM URL DISCOVERY TOOL (ALPHA PAGES)")
    print("="*70)
    
    try:
        # Discover URLs
        urls = discover_drug_urls()
        
        # Save to file
        if urls:
            count = save_urls(urls)
            print(f"📊 Total URLs collected: {count}")
            print(f"✨ Next step: python3 scraper.py --resume\n")
        else:
            print("❌ No URLs found. Please check your internet connection.\n")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Discovery interrupted by user\n")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}\n")
