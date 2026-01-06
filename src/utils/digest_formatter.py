"""Digest formatting utilities for multi-audience output."""

from src.models.digest import DigestData


class DigestFormatter:
    """Formats digests for different output types (markdown, HTML, plain text)."""

    @staticmethod
    def to_markdown(digest: DigestData) -> str:
        """Format digest as Markdown."""
        md_parts = []

        # Header
        md_parts.append(f"# {digest.title}\n")
        md_parts.append(
            f"**Period**: {digest.period_start.strftime('%B %d, %Y')} - "
            f"{digest.period_end.strftime('%B %d, %Y')}\n"
        )
        md_parts.append(f"**Newsletters Analyzed**: {digest.newsletter_count}\n")
        md_parts.append("---\n")

        # Executive Overview
        md_parts.append("## Executive Overview\n")
        md_parts.append(f"{digest.executive_overview}\n")
        md_parts.append("")

        # Strategic Insights
        if digest.strategic_insights:
            md_parts.append("## Strategic Insights\n")
            md_parts.append("*For CTOs and Technical Leaders*\n")

            for insight in digest.strategic_insights:
                # Handle both DigestSection objects and dicts
                title = insight.title if hasattr(insight, "title") else insight.get("title", "")
                summary = (
                    insight.summary if hasattr(insight, "summary") else insight.get("summary", "")
                )
                details = (
                    insight.details if hasattr(insight, "details") else insight.get("details", [])
                )
                continuity = (
                    insight.continuity
                    if hasattr(insight, "continuity")
                    else insight.get("continuity", None)
                )

                md_parts.append(f"### {title}\n")
                md_parts.append(f"{summary}\n")

                if details:
                    for detail in details:
                        md_parts.append(f"- {detail}")
                    md_parts.append("")

                if continuity:
                    md_parts.append(f"> {continuity}\n")

                md_parts.append("")

        # Technical Developments
        if digest.technical_developments:
            md_parts.append("## Technical Developments\n")
            md_parts.append("*For Developers and Practitioners*\n")

            for dev in digest.technical_developments:
                # Handle both DigestSection objects and dicts
                title = dev.title if hasattr(dev, "title") else dev.get("title", "")
                summary = dev.summary if hasattr(dev, "summary") else dev.get("summary", "")
                details = dev.details if hasattr(dev, "details") else dev.get("details", [])
                continuity = (
                    dev.continuity if hasattr(dev, "continuity") else dev.get("continuity", None)
                )

                md_parts.append(f"### {title}\n")
                md_parts.append(f"{summary}\n")

                if details:
                    for detail in details:
                        md_parts.append(f"- {detail}")
                    md_parts.append("")

                if continuity:
                    md_parts.append(f"> {continuity}\n")

                md_parts.append("")

        # Emerging Trends
        if digest.emerging_trends:
            md_parts.append("## Emerging Trends\n")
            md_parts.append("*New and Noteworthy*\n")

            for trend in digest.emerging_trends:
                # Handle both DigestSection objects and dicts
                title = trend.title if hasattr(trend, "title") else trend.get("title", "")
                summary = trend.summary if hasattr(trend, "summary") else trend.get("summary", "")
                details = trend.details if hasattr(trend, "details") else trend.get("details", [])
                continuity = (
                    trend.continuity
                    if hasattr(trend, "continuity")
                    else trend.get("continuity", None)
                )

                md_parts.append(f"### {title}\n")
                md_parts.append(f"{summary}\n")

                if details:
                    for detail in details:
                        md_parts.append(f"- {detail}")
                    md_parts.append("")

                if continuity:
                    md_parts.append(f"> 📈 {continuity}\n")

                md_parts.append("")

        # Actionable Recommendations
        if digest.actionable_recommendations:
            md_parts.append("## Actionable Recommendations\n")

            if "for_leadership" in digest.actionable_recommendations:
                md_parts.append("### For Leadership\n")
                for rec in digest.actionable_recommendations["for_leadership"]:
                    md_parts.append(f"- {rec}")
                md_parts.append("")

            if "for_teams" in digest.actionable_recommendations:
                md_parts.append("### For Teams\n")
                for rec in digest.actionable_recommendations["for_teams"]:
                    md_parts.append(f"- {rec}")
                md_parts.append("")

            if "for_individuals" in digest.actionable_recommendations:
                md_parts.append("### For Individuals\n")
                for rec in digest.actionable_recommendations["for_individuals"]:
                    md_parts.append(f"- {rec}")
                md_parts.append("")

        # Sources
        if digest.sources:
            md_parts.append("## Sources\n")
            for source in digest.sources:
                # Get newsletter ID (try both 'id' and 'newsletter_id' keys)
                newsletter_id = source.get("id") or source.get("newsletter_id", "")
                id_prefix = f"[{newsletter_id}] " if newsletter_id else ""

                if source.get("url"):
                    md_parts.append(
                        f"- {id_prefix}[{source['publication']}: {source['title']}]({source['url']}) "
                        f"({source['date']})"
                    )
                else:
                    md_parts.append(
                        f"- {id_prefix}{source['publication']}: {source['title']} ({source['date']})"
                    )
            md_parts.append("")

        # Footer
        md_parts.append("---")
        md_parts.append(
            f"*Generated on {digest.period_end.strftime('%B %d, %Y')} "
            f"using {digest.agent_framework}*"
        )

        return "\n".join(md_parts)

    @staticmethod
    def to_plain_text(digest: DigestData) -> str:
        """Format digest as plain text."""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append(digest.title.upper())
        lines.append("=" * 80)
        lines.append(
            f"Period: {digest.period_start.strftime('%B %d, %Y')} - "
            f"{digest.period_end.strftime('%B %d, %Y')}"
        )
        lines.append(f"Newsletters Analyzed: {digest.newsletter_count}")
        lines.append("=" * 80)
        lines.append("")

        # Executive Overview
        lines.append("EXECUTIVE OVERVIEW")
        lines.append("-" * 80)
        lines.append(digest.executive_overview)
        lines.append("")

        # Strategic Insights
        if digest.strategic_insights:
            lines.append("STRATEGIC INSIGHTS")
            lines.append("-" * 80)

            for i, insight in enumerate(digest.strategic_insights, 1):
                lines.append(f"\n{i}. {insight.title}")
                lines.append(f"   {insight.summary}")

                if insight.details:
                    for detail in insight.details:
                        lines.append(f"   • {detail}")

                if insight.continuity:
                    lines.append(f"   ↳ {insight.continuity}")

                lines.append("")

        # Technical Developments
        if digest.technical_developments:
            lines.append("TECHNICAL DEVELOPMENTS")
            lines.append("-" * 80)

            for i, dev in enumerate(digest.technical_developments, 1):
                lines.append(f"\n{i}. {dev.title}")
                lines.append(f"   {dev.summary}")

                if dev.details:
                    for detail in dev.details:
                        lines.append(f"   • {detail}")

                if dev.continuity:
                    lines.append(f"   ↳ {dev.continuity}")

                lines.append("")

        # Emerging Trends
        if digest.emerging_trends:
            lines.append("EMERGING TRENDS")
            lines.append("-" * 80)

            for i, trend in enumerate(digest.emerging_trends, 1):
                lines.append(f"\n{i}. {trend.title}")
                lines.append(f"   {trend.summary}")

                if trend.details:
                    for detail in trend.details:
                        lines.append(f"   • {detail}")

                if trend.continuity:
                    lines.append(f"   📈 {trend.continuity}")

                lines.append("")

        # Actionable Recommendations
        if digest.actionable_recommendations:
            lines.append("ACTIONABLE RECOMMENDATIONS")
            lines.append("-" * 80)

            if "for_leadership" in digest.actionable_recommendations:
                lines.append("\nFor Leadership:")
                for rec in digest.actionable_recommendations["for_leadership"]:
                    lines.append(f"  • {rec}")

            if "for_teams" in digest.actionable_recommendations:
                lines.append("\nFor Teams:")
                for rec in digest.actionable_recommendations["for_teams"]:
                    lines.append(f"  • {rec}")

            if "for_individuals" in digest.actionable_recommendations:
                lines.append("\nFor Individuals:")
                for rec in digest.actionable_recommendations["for_individuals"]:
                    lines.append(f"  • {rec}")

            lines.append("")

        # Sources
        if digest.sources:
            lines.append("\nSOURCES")
            lines.append("-" * 80)
            for source in digest.sources:
                # Get newsletter ID (try both 'id' and 'newsletter_id' keys)
                newsletter_id = source.get("id") or source.get("newsletter_id", "")
                id_prefix = f"[{newsletter_id}] " if newsletter_id else ""
                lines.append(
                    f"• {id_prefix}{source['publication']}: {source['title']} ({source['date']})"
                )

        lines.append("")
        lines.append("=" * 80)
        lines.append(
            f"Generated: {digest.period_end.strftime('%B %d, %Y')} | "
            f"Framework: {digest.agent_framework}"
        )

        return "\n".join(lines)

    @staticmethod
    def to_html(digest: DigestData) -> str:
        """Format digest as HTML for email delivery."""
        html_parts = []

        # HTML header with inline CSS for email compatibility
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
            font-size: 22px;
            margin-top: 30px;
            margin-bottom: 15px;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 8px;
        }
        h3 {
            color: #333;
            font-size: 18px;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        .audience-tag {
            color: #666;
            font-style: italic;
            font-size: 14px;
            margin-bottom: 15px;
        }
        .executive-overview {
            background-color: #fff8e1;
            padding: 20px;
            border-left: 4px solid #ffc107;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .section {
            margin-bottom: 30px;
            padding: 15px;
            background-color: #fafafa;
            border-radius: 4px;
        }
        .summary {
            margin-bottom: 10px;
            font-weight: 500;
        }
        ul {
            margin: 10px 0;
            padding-left: 20px;
        }
        li {
            margin-bottom: 8px;
        }
        .continuity {
            background-color: #e3f2fd;
            padding: 10px 15px;
            margin-top: 10px;
            border-left: 3px solid #2196f3;
            font-style: italic;
            color: #1565c0;
        }
        .recommendations {
            background-color: #f1f8e9;
            padding: 20px;
            border-radius: 4px;
            margin-top: 20px;
        }
        .rec-category {
            margin-bottom: 15px;
        }
        .rec-category h3 {
            color: #558b2f;
            font-size: 16px;
            margin-bottom: 8px;
        }
        .sources {
            background-color: #fafafa;
            padding: 20px;
            border-radius: 4px;
            margin-top: 20px;
        }
        .sources ul {
            list-style-type: none;
            padding-left: 0;
        }
        .sources li {
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid #e0e0e0;
        }
        .sources a {
            color: #0066cc;
            text-decoration: none;
        }
        .sources a:hover {
            text-decoration: underline;
        }
        .footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            color: #666;
            font-size: 14px;
            text-align: center;
        }
        .trend-emerging {
            display: inline-block;
            margin-right: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
""")

        # Title and metadata
        html_parts.append(f"        <h1>{digest.title}</h1>")
        html_parts.append(
            f"""        <div class="metadata">
            <strong>Period:</strong> {digest.period_start.strftime("%B %d, %Y")} - {digest.period_end.strftime("%B %d, %Y")}<br>
            <strong>Newsletters Analyzed:</strong> {digest.newsletter_count}
        </div>
"""
        )

        # Executive Overview
        html_parts.append("""        <div class="executive-overview">
            <h2>Executive Overview</h2>
""")
        # Split overview into paragraphs
        for para in digest.executive_overview.split("\n\n"):
            if para.strip():
                html_parts.append(f"            <p>{para.strip()}</p>")
        html_parts.append("        </div>")

        # Strategic Insights
        if digest.strategic_insights:
            html_parts.append("""
        <h2>Strategic Insights</h2>
        <p class="audience-tag">For CTOs and Technical Leaders</p>
""")

            for insight in digest.strategic_insights:
                # Handle both DigestSection objects and dicts
                title = insight.title if hasattr(insight, "title") else insight.get("title", "")
                summary = (
                    insight.summary if hasattr(insight, "summary") else insight.get("summary", "")
                )
                details = (
                    insight.details if hasattr(insight, "details") else insight.get("details", [])
                )
                continuity = (
                    insight.continuity
                    if hasattr(insight, "continuity")
                    else insight.get("continuity", None)
                )

                html_parts.append(f"""        <div class="section">
            <h3>{title}</h3>
            <p class="summary">{summary}</p>
""")

                if details:
                    html_parts.append("            <ul>")
                    for detail in details:
                        html_parts.append(f"                <li>{detail}</li>")
                    html_parts.append("            </ul>")

                if continuity:
                    html_parts.append(f'            <div class="continuity">{continuity}</div>')

                html_parts.append("        </div>")

        # Technical Developments
        if digest.technical_developments:
            html_parts.append("""
        <h2>Technical Developments</h2>
        <p class="audience-tag">For Developers and Practitioners</p>
""")

            for dev in digest.technical_developments:
                # Handle both DigestSection objects and dicts
                title = dev.title if hasattr(dev, "title") else dev.get("title", "")
                summary = dev.summary if hasattr(dev, "summary") else dev.get("summary", "")
                details = dev.details if hasattr(dev, "details") else dev.get("details", [])
                continuity = (
                    dev.continuity if hasattr(dev, "continuity") else dev.get("continuity", None)
                )

                html_parts.append(f"""        <div class="section">
            <h3>{title}</h3>
            <p class="summary">{summary}</p>
""")

                if details:
                    html_parts.append("            <ul>")
                    for detail in details:
                        html_parts.append(f"                <li>{detail}</li>")
                    html_parts.append("            </ul>")

                if continuity:
                    html_parts.append(f'            <div class="continuity">{continuity}</div>')

                html_parts.append("        </div>")

        # Emerging Trends
        if digest.emerging_trends:
            html_parts.append("""
        <h2>Emerging Trends</h2>
        <p class="audience-tag">New and Noteworthy</p>
""")

            for trend in digest.emerging_trends:
                # Handle both DigestSection objects and dicts
                title = trend.title if hasattr(trend, "title") else trend.get("title", "")
                summary = trend.summary if hasattr(trend, "summary") else trend.get("summary", "")
                details = trend.details if hasattr(trend, "details") else trend.get("details", [])
                continuity = (
                    trend.continuity
                    if hasattr(trend, "continuity")
                    else trend.get("continuity", None)
                )

                html_parts.append(f"""        <div class="section">
            <h3><span class="trend-emerging">📈</span>{title}</h3>
            <p class="summary">{summary}</p>
""")

                if details:
                    html_parts.append("            <ul>")
                    for detail in details:
                        html_parts.append(f"                <li>{detail}</li>")
                    html_parts.append("            </ul>")

                if continuity:
                    html_parts.append(f'            <div class="continuity">📈 {continuity}</div>')

                html_parts.append("        </div>")

        # Actionable Recommendations
        if digest.actionable_recommendations:
            html_parts.append("""
        <div class="recommendations">
            <h2>Actionable Recommendations</h2>
""")

            if "for_leadership" in digest.actionable_recommendations:
                html_parts.append("""            <div class="rec-category">
                <h3>For Leadership</h3>
                <ul>
""")
                for rec in digest.actionable_recommendations["for_leadership"]:
                    html_parts.append(f"                    <li>{rec}</li>")
                html_parts.append("                </ul>\n            </div>")

            if "for_teams" in digest.actionable_recommendations:
                html_parts.append("""            <div class="rec-category">
                <h3>For Teams</h3>
                <ul>
""")
                for rec in digest.actionable_recommendations["for_teams"]:
                    html_parts.append(f"                    <li>{rec}</li>")
                html_parts.append("                </ul>\n            </div>")

            if "for_individuals" in digest.actionable_recommendations:
                html_parts.append("""            <div class="rec-category">
                <h3>For Individuals</h3>
                <ul>
""")
                for rec in digest.actionable_recommendations["for_individuals"]:
                    html_parts.append(f"                    <li>{rec}</li>")
                html_parts.append("                </ul>\n            </div>")

            html_parts.append("        </div>")

        # Sources
        if digest.sources:
            html_parts.append("""
        <div class="sources">
            <h2>Sources</h2>
            <ul>
""")
            for source in digest.sources:
                # Get newsletter ID (try both 'id' and 'newsletter_id' keys)
                newsletter_id = source.get("id") or source.get("newsletter_id", "")
                id_prefix = f"[{newsletter_id}] " if newsletter_id else ""

                if source.get("url"):
                    html_parts.append(
                        f'                <li>{id_prefix}<a href="{source["url"]}">'
                        f"{source['publication']}: {source['title']}</a> "
                        f'<span style="color: #666;">({source["date"]})</span></li>'
                    )
                else:
                    html_parts.append(
                        f"                <li>{id_prefix}{source['publication']}: {source['title']} "
                        f'<span style="color: #666;">({source["date"]})</span></li>'
                    )
            html_parts.append("            </ul>\n        </div>")

        # Footer
        html_parts.append(
            f"""
        <div class="footer">
            Generated on {digest.period_end.strftime("%B %d, %Y")} using {digest.agent_framework}
        </div>
    </div>
</body>
</html>"""
        )

        return "\n".join(html_parts)
