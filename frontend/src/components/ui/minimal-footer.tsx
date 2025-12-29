import {
	GithubIcon,
	LinkedinIcon,
	TwitterIcon,
} from 'lucide-react';

export function MinimalFooter() {
	const year = new Date().getFullYear();

	const company = [
		{
			title: 'About',
			href: '#',
		},
		{
			title: 'Privacy Policy',
			href: '#',
		},
		{
			title: 'Terms of Service',
			href: '#',
		},
	];

	const resources = [
		{
			title: 'Help Center',
			href: '#',
		},
		{
			title: 'Contact Support',
			href: '#',
		},
	];

	const socialLinks = [
		{
			icon: <TwitterIcon className="size-4" />,
			link: '#',
		},
		{
			icon: <LinkedinIcon className="size-4" />,
			link: '#',
		},
		{
			icon: <GithubIcon className="size-4" />,
			link: '#',
		},
	];

	return (
		<footer className="relative mt-24">
			<div className="bg-[radial-gradient(35%_80%_at_30%_0%,--theme(--color-foreground/.1),transparent)] mx-auto max-w-4xl md:border-x">
				<div className="bg-border absolute inset-x-0 h-px w-full" />
				<div className="grid max-w-4xl grid-cols-6 gap-6 p-8">
					<div className="col-span-6 flex flex-col gap-5 md:col-span-4">
						<a href="/" className="flex items-center gap-2">
							<span className="text-2xl font-extralight lowercase tracking-tighter">amplify</span>
						</a>
						<p className="text-muted-foreground max-w-sm font-light text-sm text-balance">
							Find leads faster with natural language. AI-powered enrichment for modern sales teams.
						</p>
						<div className="flex gap-2">
							{socialLinks.map((item, i) => (
								<a
									key={i}
									className="hover:bg-accent hover:text-foreground text-muted-foreground rounded-md border p-2 transition-colors"
									target="_blank"
									href={item.link}
								>
									{item.icon}
								</a>
							))}
						</div>
					</div>
					<div className="col-span-3 w-full md:col-span-1">
						<span className="text-foreground mb-4 block text-sm font-medium">
							Resources
						</span>
						<div className="flex flex-col gap-2">
							{resources.map(({ href, title }, i) => (
								<a
									key={i}
									className={`w-max text-sm text-muted-foreground hover:text-foreground duration-200 hover:underline`}
									href={href}
								>
									{title}
								</a>
							))}
						</div>
					</div>
					<div className="col-span-3 w-full md:col-span-1">
						<span className="text-foreground mb-4 block text-sm font-medium">Company</span>
						<div className="flex flex-col gap-2">
							{company.map(({ href, title }, i) => (
								<a
									key={i}
									className={`w-max text-sm text-muted-foreground hover:text-foreground duration-200 hover:underline`}
									href={href}
								>
									{title}
								</a>
							))}
						</div>
					</div>
				</div>
				<div className="bg-border absolute inset-x-0 h-px w-full" />
				<div className="flex max-w-4xl flex-col justify-between gap-2 py-6">
					<p className="text-muted-foreground text-center text-sm font-light">
						© {year} Amplify. All rights reserved.
					</p>
				</div>
			</div>
		</footer>
	);
}
