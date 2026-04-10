#!/usr/bin/env python3
from __future__ import annotations

import sys
import re
from pathlib import Path


PREAMBLE_OLD = r"""\setcounter{secnumdepth}{-\maxdimen} % remove section numbering

\title{LLM-Enhanced Disk Failure Prediction on Top of StreamDFP: System
Design, Evaluation, and First-Term Progress}
\author{Student Name: Daoyang LIU\\
Student ID: 1155244610\\
Master of Science in Artificial Intelligence\\
AIMS5790 Artificial Intelligence Project I}
\date{April 2026}
"""

PREAMBLE_PREV = r"""\setcounter{secnumdepth}{-\maxdimen} % remove section numbering
\usepackage{caption}
\usepackage{float}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage{enumitem}
\captionsetup{font=small,labelfont=bf}
\setlist{itemsep=0.3em, topsep=0.3em}
\titleformat{\section}{\Large\bfseries}{}{0pt}{}
\titleformat{\subsection}{\large\bfseries}{}{0pt}{}
\titleformat{\subsubsection}{\normalsize\bfseries}{}{0pt}{}
\titlespacing*{\section}{0pt}{1.4em}{0.6em}
\titlespacing*{\subsection}{0pt}{1.0em}{0.45em}
\titlespacing*{\subsubsection}{0pt}{0.8em}{0.3em}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0pt}
\setlength{\headheight}{14pt}

\title{LLM-Enhanced Disk Failure Prediction on Top of StreamDFP: System
Design, Evaluation, and First-Term Progress}
\author{Student Name: Daoyang LIU\\
Student ID: 1155244610\\
Master of Science in Artificial Intelligence\\
AIMS5790 Artificial Intelligence Project I}
\date{April 2026}
"""


PREAMBLE_NEW = r"""\setcounter{secnumdepth}{-\maxdimen} % remove section numbering
\usepackage{caption}
\usepackage{float}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage{enumitem}
\captionsetup{font=small,labelfont=bf,skip=4pt}
\setlist{itemsep=0.3em, topsep=0.3em}
\titleformat{\section}{\Large\bfseries}{}{0pt}{}
\titleformat{\subsection}{\large\bfseries}{}{0pt}{}
\titleformat{\subsubsection}{\normalsize\bfseries}{}{0pt}{}
\titlespacing*{\section}{0pt}{1.0em}{0.4em}
\titlespacing*{\subsection}{0pt}{0.8em}{0.3em}
\titlespacing*{\subsubsection}{0pt}{0.6em}{0.25em}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0pt}
\setlength{\headheight}{14pt}
\setlength{\textfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\floatsep}{8pt plus 2pt minus 2pt}
\setlength{\intextsep}{8pt plus 2pt minus 2pt}
\setlength{\abovecaptionskip}{4pt}
\setlength{\belowcaptionskip}{0pt}
\setlength{\LTpre}{6pt}
\setlength{\LTpost}{6pt}
\AtBeginEnvironment{longtable}{\small\setlength{\tabcolsep}{4pt}\renewcommand{\arraystretch}{1.08}}
\AtEndEnvironment{longtable}{\normalsize\renewcommand{\arraystretch}{1.0}}

\title{LLM-Enhanced Disk Failure Prediction on Top of StreamDFP: System
Design, Evaluation, and First-Term Progress}
\author{Student Name: Daoyang LIU\\
Student ID: 1155244610\\
Master of Science in Artificial Intelligence\\
AIMS5790 Artificial Intelligence Project I}
\date{April 2026}
"""


BODY_OLD = r"""\begin{document}
\maketitle

{
\setcounter{tocdepth}{3}
\tableofcontents
}
\setstretch{1.0}
"""

BODY_PREV = r"""\begin{document}
\begin{titlepage}
\thispagestyle{empty}
\centering
\vspace*{1.8cm}
{\Large AIMS5790 Artificial Intelligence Project I\par}
\vspace{1.2cm}
{\large Master of Science in Artificial Intelligence\par}
\vspace{1.6cm}
{\Huge \bfseries LLM-Enhanced Disk Failure Prediction on Top of StreamDFP\par}
\vspace{0.35cm}
{\Large \bfseries System Design, Evaluation, and First-Term Progress\par}
\vfill
{\large Student Name: Daoyang LIU\par}
\vspace{0.3cm}
{\large Student ID: 1155244610\par}
\vspace{1.0cm}
{\large Faculty of Engineering\par}
{\large The Chinese University of Hong Kong\par}
\vspace{1.2cm}
{\large April 2026\par}
\end{titlepage}

\pagenumbering{roman}
{
\setcounter{tocdepth}{3}
\tableofcontents
}
\clearpage
\pagenumbering{arabic}
\setstretch{1.0}
"""


BODY_NEW = r"""\begin{document}
\hypersetup{pageanchor=false}
\begin{titlepage}
\thispagestyle{empty}
\centering
\vspace*{1.2cm}
{\Large AIMS5790 Artificial Intelligence Project I\par}
\vspace{0.8cm}
{\large Master of Science in Artificial Intelligence\par}
\vspace{1.1cm}
{\Huge \bfseries LLM-Enhanced Disk Failure Prediction on Top of StreamDFP\par}
\vspace{0.25cm}
{\Large \bfseries System Design, Evaluation, and First-Term Progress\par}
\vfill
{\large Student Name: Daoyang LIU\par}
\vspace{0.2cm}
{\large Student ID: 1155244610\par}
\vspace{0.8cm}
{\large Faculty of Engineering\par}
{\large The Chinese University of Hong Kong\par}
\vspace{0.8cm}
{\large April 2026\par}
\end{titlepage}

\hypersetup{pageanchor=true}
\pagenumbering{roman}
{
\setcounter{tocdepth}{2}
\footnotesize
\setstretch{0.94}
\setlength{\parskip}{0pt}
\tableofcontents
}
\clearpage
\pagenumbering{arabic}
\setstretch{1.0}
"""


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: postprocess_report_tex.py <tex-path>")

    path = Path(sys.argv[1]).resolve()
    text = path.read_text()

    for candidate in (PREAMBLE_OLD, PREAMBLE_PREV):
        if candidate in text:
            text = text.replace(candidate, PREAMBLE_NEW, 1)
            break

    for candidate in (BODY_OLD, BODY_PREV):
        if candidate in text:
            text = text.replace(candidate, BODY_NEW, 1)
            break

    text = text.replace(r"\usepackage{lmodern}", r"\usepackage{mathptmx}", 1)
    text = re.sub(r"\\caption\{Figure\s+\d+\.\s*", r"\\caption{", text)
    text = text.replace(
        r"\DefineVerbatimEnvironment{Highlighting}{Verbatim}{commandchars=\\\{\}}",
        r"\DefineVerbatimEnvironment{Highlighting}{Verbatim}{commandchars=\\\{\},fontsize=\footnotesize}",
    )

    path.write_text(text)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
