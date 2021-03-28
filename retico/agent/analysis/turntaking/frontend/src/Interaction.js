import React, { Component, useState } from "react";
import { Navbar, Nav, NavDropdown, Tab, Tabs } from "react-bootstrap";

import Dialog from "./Dialog";
import Annotation from "./Annotation";
import ChatAgent from "./ChatAgent";
import Global from "./Global";
import Aggregate from "./Aggregate";

import "bootstrap/dist/css/bootstrap.min.css";

const rootURL = "/api/roots";
// thses endpoints have stupid names
const interactionsURL = "/api/interactions";
const interactionURL = "/api/interaction";

const Navigation = (props) => {
	const [key, setKey] = useState("dialog");

	const items = props.interactions.map((s, i) => {
		return (
			<NavDropdown.Item eventKey={s} key={i}>
				{" "}
				{s}{" "}
			</NavDropdown.Item>
		);
	});

	const rootItems = props.roots.map((s, i) => {
		return (
			<NavDropdown.Item eventKey={s} key={i}>
				{" "}
				{s}{" "}
			</NavDropdown.Item>
		);
	});

	console.log(props.currentRoot);

	let styles = { background: "#eaeaea" };
	return (
		<Navbar expand="sm" style={styles}>
			<Navbar.Collapse id="basic-navbar-nav">
				<Tabs
					activeKey={key}
					onSelect={(k) => {
						props.onChangeContent(k);
						setKey(k);
					}}
					className="mr-auto"
				>
					<Tab eventKey="dialog" title="Dialog" />
					<Tab eventKey="global" title="Global" />
					<Tab eventKey="aggregate" title="Aggregate" />
					<Tab eventKey="annotation" title="Annotation" />
					<Tab eventKey="chatagent" title="Chat" />
					<Tab eventKey="hparams" title="Hparams" />
				</Tabs>
				<Nav
					activeKey={props.activeRootKey}
					// onSelect={(key) => props.onChangeInteraction(key)}
					className="justify-content-end"
				>
					<NavDropdown title={props.currentRoot} size="sm" drop="left">
						{rootItems}
					</NavDropdown>
				</Nav>
				<Nav
					activeKey={props.activeKey}
					onSelect={(key) => props.onChangeInteraction(key)}
					className="justify-content-end"
				>
					<NavDropdown title={props.currentInteraction} size="sm" drop="left">
						{items}
					</NavDropdown>
				</Nav>
			</Navbar.Collapse>
		</Navbar>
	);
};

class Hparams extends Component {
	constructor(props) {
		super(props);
		this.state = {
			hparams: null,
		};
	}
	componentDidMount() {
		fetch(interactionURL + "/hparams/" + this.props.interaction)
			.then((response) => response.json())
			.then((data) => {
				this.setState({ hparams: data });
			});
	}

	getHparams() {
		if (this.state.hparams === null) {
			return;
		}
		console.log(this.state.hparams);
		let hparams = Object.entries(this.state.hparams).map((value, i) => {
			return (
				<li key={value}>
					{" "}
					{value[0]}: {value[1]}
				</li>
			);
		});
		return hparams;
	}
	render() {
		const hparams = this.getHparams();
		return <ul> {hparams} </ul>;
	}
}

export default class Interaction extends Component {
	constructor(props) {
		super(props);
		this.state = {
			content: "dialog",
			interaction: "",
			interactions: [],
			root: "",
			roots: [],
			hparams: null,
			activeKeyDropdown: 0,
			activeRootKeyDropdown: 0,
		};
		this.onChangeContent = this.onChangeContent.bind(this);
		this.onChangeInteraction = this.onChangeInteraction.bind(this);
	}

	componentDidMount() {
		fetch(interactionsURL)
			.then((response) => response.json())
			.then((data) => {
				this.setState({
					interactions: data.interactions,
					interaction: data.interactions[0],
				});
			});
		fetch(rootURL)
			.then((response) => response.json())
			.then((data) => {
				console.log(data);
				this.setState({
					roots: data.roots,
					root: data.roots[0],
				});
			});
	}

	onChangeContent(content) {
		this.setState({ content: content });
	}

	onChangeInteraction(interaction) {
		console.log("interaction: " + interaction);
		this.setState({
			interaction: interaction,
		});
	}

	getContent() {
		let content;
		if (this.state.content === "global") {
			content = (
				<Global
					interaction={this.state.interaction}
					key={this.state.interaction}
				/>
			);
		} else if (this.state.content === "annotation") {
			content = <Annotation />;
		} else if (this.state.content === "chatagent") {
			content = <ChatAgent />;
		} else if (this.state.content === "hparams") {
			content = <Hparams interaction={this.state.interaction} key="hparams" />;
		} else if (this.state.content === "aggregate") {
			content = <Aggregate root={this.state.root} />;
		} else {
			content = (
				<Dialog
					interaction={this.state.interaction}
					key={this.state.interaction}
				/>
			);
		}
		return content;
	}

	render() {
		// const content = this.getContent();
		return (
			<div>
				<Navigation
					onChangeContent={this.onChangeContent}
					onChangeInteraction={this.onChangeInteraction}
					activeKey={this.state.activeKeyDropdown}
					interactions={this.state.interactions}
					currentInteraction={this.state.interaction}
					activeRootKey={this.state.activeRootKeyDropdown}
					roots={this.state.roots}
					currentRoot={this.state.root}
				/>
				{this.getContent()}
			</div>
		);
	}
}
