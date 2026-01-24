"""Summary formatting utilities for multi-format output."""

from src.models.newsletter import Newsletter
from src.models.summary import Summary


class SummaryFormatter:
    """Formats newsletter summaries for different output types (markdown, HTML, plain text)."""

    @staticmethod
    def to_plain_text(summary: Summary, newsletter: Newsletter) -> str:
        """Format summary as plain text."""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("NEWSLETTER SUMMARY")
        lines.append("=" * 80)
        lines.append(f"Title: {newsletter.title}")
        lines.append(f"Publication: {newsletter.publication or 'N/A'}")
        lines.append(f"Published: {newsletter.published_date.strftime('%B %d, %Y %H:%M')}")
        if newsletter.url:
            lines.append(f"URL: {newsletter.url}")
        lines.append("=" * 80)
        lines.append("")

        # Executive Summary
        lines.append("EXECUTIVE SUMMARY")
        lines.append("-" * 80)
        lines.append(summary.executive_summary)
        lines.append("")

        # Key Themes
        if summary.key_themes:
            lines.append("KEY THEMES")
            lines.append("-" * 80)
            for theme in summary.key_themes:
                lines.append(f"  • {theme}")
            lines.append("")

        # Strategic Insights
        if summary.strategic_insights:
            lines.append("STRATEGIC INSIGHTS")
            lines.append("-" * 80)
            for insight in summary.strategic_insights:
                lines.append(f"  • {insight}")
            lines.append("")

        # Technical Details
        if summary.technical_details:
            lines.append("TECHNICAL DETAILS")
            lines.append("-" * 80)
            for detail in summary.technical_details:
                lines.append(f"  • {detail}")
            lines.append("")

        # Actionable Items
        if summary.actionable_items:
            lines.append("ACTIONABLE ITEMS")
            lines.append("-" * 80)
            for item in summary.actionable_items:
                lines.append(f"  • {item}")
            lines.append("")

        # Notable Quotes
        if summary.notable_quotes:
            lines.append("NOTABLE QUOTES")
            lines.append("-" * 80)
            for quote in summary.notable_quotes:
                lines.append(f'  "{quote}"')
            lines.append("")

        # Relevant Links
        if summary.relevant_links:
            lines.append("RELEVANT LINKS")
            lines.append("-" * 80)
            for link in summary.relevant_links:
                title = link.get("title", "Untitled")
                url = link.get("url", "")
                lines.append(f"  • {title}")
                lines.append(f"    {url}")
            lines.append("")

        # Relevance Scores
        if summary.relevance_scores:
            lines.append("RELEVANCE SCORES")
            lines.append("-" * 80)
            for category, score in summary.relevance_scores.items():
                lines.append(f"  {category.replace('_', ' ').title()}: {score:.2f}")
            lines.append("")

        # Processing Metadata
        lines.append("PROCESSING METADATA")
        lines.append("-" * 80)
        lines.append(f"Model: {summary.model_used}")
        if summary.model_version:
            lines.append(f"Version: {summary.model_version}")
        lines.append(f"Framework: {summary.agent_framework}")
        if summary.token_usage:
            lines.append(f"Tokens: {summary.token_usage:,}")
        if summary.processing_time_seconds:
            lines.append(f"Processing Time: {summary.processing_time_seconds:.2f}s")
        lines.append(f"Created: {summary.created_at.strftime('%B %d, %Y %H:%M')}")
        lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    @staticmethod
    def to_markdown(summary: Summary, newsletter: Newsletter) -> str:
        """Format summary as Markdown."""
        md_parts = []

        # Header
        md_parts.append(f"# {newsletter.title}\n")
        md_parts.append(f"**Publication**: {newsletter.publication or 'N/A'}  ")
        md_parts.append(f"**Published**: {newsletter.published_date.strftime('%B %d, %Y %H:%M')}  ")
        if newsletter.url:
            md_parts.append(f"**URL**: {newsletter.url}  ")
        md_parts.append("\n---\n")

        # Executive Summary
        md_parts.append("## Executive Summary\n")
        md_parts.append(f"{summary.executive_summary}\n")

        # Key Themes
        if summary.key_themes:
            md_parts.append("## Key Themes\n")
            for theme in summary.key_themes:
                md_parts.append(f"- {theme}")
            md_parts.append("")

        # Strategic Insights
        if summary.strategic_insights:
            md_parts.append("## Strategic Insights\n")
            md_parts.append("*For CTOs and Technical Leaders*\n")
            for insight in summary.strategic_insights:
                md_parts.append(f"- {insight}")
            md_parts.append("")

        # Technical Details
        if summary.technical_details:
            md_parts.append("## Technical Details\n")
            md_parts.append("*For Developers and Practitioners*\n")
            for detail in summary.technical_details:
                md_parts.append(f"- {detail}")
            md_parts.append("")

        # Actionable Items
        if summary.actionable_items:
            md_parts.append("## Actionable Items\n")
            for item in summary.actionable_items:
                md_parts.append(f"- {item}")
            md_parts.append("")

        # Notable Quotes
        if summary.notable_quotes:
            md_parts.append("## Notable Quotes\n")
            for quote in summary.notable_quotes:
                md_parts.append(f"> {quote}\n")
            md_parts.append("")

        # Relevant Links
        if summary.relevant_links:
            md_parts.append("## Relevant Links\n")
            for link in summary.relevant_links:
                title = link.get("title", "Untitled")
                url = link.get("url", "")
                md_parts.append(f"- [{title}]({url})")
            md_parts.append("")

        # Relevance Scores
        if summary.relevance_scores:
            md_parts.append("## Relevance Scores\n")
            for category, score in summary.relevance_scores.items():
                md_parts.append(f"- **{category.replace('_', ' ').title()}**: {score:.2f}")
            md_parts.append("")

        # Footer
        md_parts.append("---")
        md_parts.append(
            f"*Summarized on {summary.created_at.strftime('%B %d, %Y %H:%M')} using {summary.agent_framework} "
            f"({summary.model_used})*"
        )
        if summary.token_usage or summary.processing_time_seconds:
            metadata_parts = []
            if summary.token_usage:
                metadata_parts.append(f"{summary.token_usage:,} tokens")
            if summary.processing_time_seconds:
                metadata_parts.append(f"{summary.processing_time_seconds:.2f}s")
            md_parts.append(f"*{', '.join(metadata_parts)}*")

        return "\n".join(md_parts)

    @staticmethod
    def to_html(summary: Summary, newsletter: Newsletter) -> str:
        """Format summary as HTML for email delivery or web display."""
        html_parts = []

        # HTML header with inline CSS
        html_parts.append("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #1a1a1a;
            font-size: 28px;
            margin-bottom: 10px;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
        }
        .metadata {
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
            padding: 10px;
            background-color: #f8f9fa;
            border-left: 4px solid #0066cc;
        }
        h2 {
            color: #0066cc;
            font-size: 20px;
            margin-top: 25px;
            margin-bottom: 12px;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 6px;
        }
        .audience-tag {
            color: #666;
            font-style: italic;
            font-size: 14px;
            margin-bottom: 10px;
        }
        .executive-summary {
            background-color: #fff8e1;
            padding: 20px;
            border-left: 4px solid #ffc107;
            margin-bottom: 20px;
            border-radius: 4px;
            font-size: 16px;
        }
        ul {
            margin: 10px 0;
            padding-left: 25px;
        }
        li {
            margin-bottom: 8px;
        }
        .quote {
            border-left: 3px solid #0066cc;
            padding-left: 15px;
            margin: 10px 0;
            font-style: italic;
            color: #555;
        }
        .links a {
            color: #0066cc;
            text-decoration: none;
        }
        .links a:hover {
            text-decoration: underline;
        }
        .scores {
            background-color: #f1f8e9;
            padding: 15px;
            border-radius: 4px;
            margin-top: 15px;
        }
        .score-item {
            margin-bottom: 8px;
        }
        .score-bar {
            display: inline-block;
            background-color: #558b2f;
            height: 8px;
            border-radius: 4px;
            margin-left: 10px;
        }
        .footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            color: #666;
            font-size: 13px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
""")

        # Title and metadata
        html_parts.append(f"        <h1>{newsletter.title}</h1>")
        html_parts.append(f"""        <div class="metadata">
            <strong>Publication:</strong> {newsletter.publication or "N/A"}<br>
            <strong>Published:</strong> {newsletter.published_date.strftime("%B %d, %Y %H:%M")}<br>
""")
        if newsletter.url:
            html_parts.append(
                f'            <strong>URL:</strong> <a href="{newsletter.url}">{newsletter.url}</a><br>'
            )
        html_parts.append("        </div>\n")

        # Executive Summary
        html_parts.append("""        <div class="executive-summary">
            <h2>Executive Summary</h2>
""")
        # Split summary into paragraphs
        for para in summary.executive_summary.split("\n\n"):
            if para.strip():
                html_parts.append(f"            <p>{para.strip()}</p>")
        html_parts.append("        </div>\n")

        # Key Themes
        if summary.key_themes:
            html_parts.append("        <h2>Key Themes</h2>\n        <ul>")
            for theme in summary.key_themes:
                html_parts.append(f"            <li>{theme}</li>")
            html_parts.append("        </ul>\n")

        # Strategic Insights
        if summary.strategic_insights:
            html_parts.append("""        <h2>Strategic Insights</h2>
        <p class="audience-tag">For CTOs and Technical Leaders</p>
        <ul>""")
            for insight in summary.strategic_insights:
                html_parts.append(f"            <li>{insight}</li>")
            html_parts.append("        </ul>\n")

        # Technical Details
        if summary.technical_details:
            html_parts.append("""        <h2>Technical Details</h2>
        <p class="audience-tag">For Developers and Practitioners</p>
        <ul>""")
            for detail in summary.technical_details:
                html_parts.append(f"            <li>{detail}</li>")
            html_parts.append("        </ul>\n")

        # Actionable Items
        if summary.actionable_items:
            html_parts.append("        <h2>Actionable Items</h2>\n        <ul>")
            for item in summary.actionable_items:
                html_parts.append(f"            <li>{item}</li>")
            html_parts.append("        </ul>\n")

        # Notable Quotes
        if summary.notable_quotes:
            html_parts.append("        <h2>Notable Quotes</h2>")
            for quote in summary.notable_quotes:
                html_parts.append(f'        <div class="quote">{quote}</div>')
            html_parts.append("")

        # Relevant Links
        if summary.relevant_links:
            html_parts.append('        <h2>Relevant Links</h2>\n        <ul class="links">')
            for link in summary.relevant_links:
                title = link.get("title", "Untitled")
                url = link.get("url", "")
                html_parts.append(f'            <li><a href="{url}">{title}</a></li>')
            html_parts.append("        </ul>\n")

        # Relevance Scores
        if summary.relevance_scores:
            html_parts.append('        <div class="scores">\n            <h2>Relevance Scores</h2>')
            for category, score in summary.relevance_scores.items():
                bar_width = int(score * 150)  # Max 150px
                html_parts.append(f"""            <div class="score-item">
                <strong>{category.replace("_", " ").title()}:</strong> {score:.2f}
                <span class="score-bar" style="width: {bar_width}px;"></span>
            </div>""")
            html_parts.append("        </div>\n")

        # Footer
        html_parts.append(f"""        <div class="footer">
            Summarized on {summary.created_at.strftime("%B %d, %Y %H:%M")} using {summary.agent_framework} ({summary.model_used})""")
        if summary.token_usage or summary.processing_time_seconds:
            metadata_parts = []
            if summary.token_usage:
                metadata_parts.append(f"{summary.token_usage:,} tokens")
            if summary.processing_time_seconds:
                metadata_parts.append(f"{summary.processing_time_seconds:.2f}s")
            html_parts.append(f"<br>{', '.join(metadata_parts)}")
        html_parts.append("""
        </div>
    </div>
</body>
</html>""")

        return "\n".join(html_parts)
