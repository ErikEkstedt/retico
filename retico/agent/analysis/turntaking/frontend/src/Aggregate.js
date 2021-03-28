import React, { Component } from "react";
import { Container, Row, Col } from "react-bootstrap";
import Plot from "react-plotly.js";

const baseUrl = "/api/aggregate";

export default class Aggregate extends Component {
	constructor(props) {
		super(props);
		this.state = {
			stats: null,
			root: props.root,
			tfoBins: 10,
			tfoBinSize: 0.1,
			tfoBinEnd: 3.1,
		};
	}

	componentDidMount() {
		// fetch(baseUrl+'/stats').then(response => response.json()).then((data) => {
		//   this.setState({stats: data})
		// });
		fetch(baseUrl + "/" + this.state.root)
			.then((response) => response.json())
			.then((data) => {
				this.setState({ stats: data });
			});
	}

	getTFO() {
		if (this.state.stats === null) {
			return;
		}

		let data = [];
		if (this.state.stats.baseline !== undefined) {
			data.push({
				x: this.state.stats.baseline.tfo.agent.tfo,
				type: "histogram",
				histnorm: "probability",
				name: "baseline",
				xbins: {
					end: this.state.tfoBinEnd,
					size: this.state.tfoBinSize,
					start: 0,
				},
			});
		}

		if (this.state.stats.prediction !== undefined) {
			data.push({
				x: this.state.stats.prediction.tfo.agent.tfo,
				type: "histogram",
				histnorm: "probability",
				name: "prediction",
				xbins: {
					end: this.state.tfoBinEnd,
					size: this.state.tfoBinSize,
					start: 0,
				},
			});
		}

		if (this.state.stats.baselinevad !== undefined) {
			data.push({
				x: this.state.stats.baselinevad.tfo.agent.tfo,
				type: "histogram",
				histnorm: "probability",
				name: "baselinevad",
				xbins: {
					end: this.state.tfoBinEnd,
					size: this.state.tfoBinSize,
					start: 0,
				},
			});
		}

		return <Plot data={data} />;
	}

	getGrades() {
		if (this.state.stats === null || this.state.stats === undefined) {
			return;
		}

		let y = ["responsiveness", "natural", "enjoyment"];

		let data = [];
		try {
			let baseline_x = [
				this.state.stats.baseline.grades.responsiveness.mean,
				this.state.stats.baseline.grades.natural.mean,
				this.state.stats.baseline.grades.enjoyment.mean,
			];
			data.push({ y: baseline_x, x: y, type: "bar", name: "baseline" });
		} catch (err) {
			console.log("baseline grades not found");
		}

		try {
			let baselinevad_x = [
				this.state.stats.baselinevad.grades.responsiveness.mean,
				this.state.stats.baselinevad.grades.natural.mean,
				this.state.stats.baselinevad.grades.enjoyment.mean,
			];
			data.push({ y: baselinevad_x, x: y, type: "bar", name: "baselinevad" });
		} catch (err) {
			console.log("baselinevad grades not found");
		}

		try {
			let prediction_x = [
				this.state.stats.prediction.grades.responsiveness.mean,
				this.state.stats.prediction.grades.natural.mean,
				this.state.stats.prediction.grades.enjoyment.mean,
			];
			data.push({ y: prediction_x, x: y, type: "bar", name: "prediction" });
		} catch (err) {
			console.log("baselinevad grades not found");
		}
		return <Plot data={data} />;
	}

	getAnnotation() {
		if (this.state.stats === null) {
			return;
		}

		let y = ["interruption", "missed-eot"];

		let data = [];
		try {
			let baseline_x = [
				this.state.stats.baseline.anno.interruption.mean,
				this.state.stats.baseline.anno.missed_eot.mean,
			];
			data.push({ y: baseline_x, x: y, type: "bar", name: "baseline" });
		} catch (err) {
			console.log("baseline anno not found");
		}

		try {
			let baselinevad_x = [
				this.state.stats.baselinevad.anno.interruption.mean,
				this.state.stats.baselinevad.anno.missed_eot.mean,
			];
			data.push({ y: baselinevad_x, x: y, type: "bar", name: "baselinevad" });
		} catch (err) {
			console.log("baselinevad anno not found");
		}

		try {
			let prediction_x = [
				this.state.stats.prediction.anno.interruption.mean,
				this.state.stats.prediction.anno.missed_eot.mean,
			];
			data.push({ y: prediction_x, x: y, type: "bar", name: "prediction" });
		} catch (err) {
			console.log("prediction anno not found");
		}

		return <Plot data={data} />;
	}

	render() {
		const tfo = this.getTFO();
		const grades = this.getGrades();
		const anno = this.getAnnotation();
		// const grades = null;
		// const anno = null;
		// console.log(this.state.stats)
		return (
			<Container fluid style={{ background: "#778ca3", textAlign: "center" }}>
				<Row>
					<Col>
						<h3>TFO</h3>
						{tfo}
						<h3>Grades</h3>
						{grades}
						<h3>Anno</h3>
						{anno}
					</Col>
				</Row>
			</Container>
		);
	}
}
